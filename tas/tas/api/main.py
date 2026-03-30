"""FastAPIアプリケーション（POCUS）"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from tas.api.limiter import limiter
from tas.api.routes import admin, map, sheets, tournament, venue
from tas.config import settings
from tas.constants import VERSION
from tas.db.session import AsyncSessionLocal
from tas.db.session import engine as db_engine

logger = logging.getLogger(__name__)


async def _crawler_scheduler() -> None:
    """バックグラウンドで定期クロールを実行するループ"""
    from tas.crawler.engine import CrawlEngine

    logger.info(
        f"[SCHEDULER] started — interval={settings.scheduler_interval_minutes}min, "
        f"batch={settings.scheduler_batch_size}"
    )
    while True:
        try:
            async with AsyncSessionLocal() as session:
                try:
                    crawler = CrawlEngine(session)
                    count = await crawler.run(limit=settings.scheduler_batch_size)
                    await session.commit()
                    logger.info("[SCHEDULER] ran %d source(s)", count)
                except Exception:
                    await session.rollback()
                    raise
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("[SCHEDULER] error: %s", e, exc_info=True)
        await asyncio.sleep(settings.scheduler_interval_minutes * 60)


async def _discovery_scheduler() -> None:
    """バックグラウンドで定期的に新店舗を自動発見するループ"""
    from tas.crawler.web_search import discover_new_directories, search_discover, seed_directory_sources

    interval = settings.discovery_interval_hours * 3600
    logger.info(
        f"[DISCOVERY] started — interval={settings.discovery_interval_hours}h"
    )
    while True:
        try:
            async with AsyncSessionLocal() as session:
                try:
                    dir_count = await seed_directory_sources(session)
                    new_dir_count = await discover_new_directories(session)
                    search_count = await search_discover(session)
                    logger.info(
                        f"[DISCOVERY] directories={dir_count}, "
                        f"new_directories={new_dir_count}, search={search_count}"
                    )
                except Exception:
                    await session.rollback()
                    raise
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("[DISCOVERY] error: %s", e, exc_info=True)
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    scheduler_task: asyncio.Task | None = None
    discovery_task: asyncio.Task | None = None

    if settings.scheduler_enabled:
        scheduler_task = asyncio.create_task(_crawler_scheduler())
    if settings.discovery_enabled:
        discovery_task = asyncio.create_task(_discovery_scheduler())

    yield

    for task in (scheduler_task, discovery_task):
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    await db_engine.dispose()


app = FastAPI(
    title="POCUS API",
    description="ポーカー店舗情報集約システム API",
    version=VERSION,
    debug=False,
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_CORS_ORIGINS = (
    [o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()]
    if settings.cors_allowed_origins
    else [o.strip() for o in settings.cors_fallback_origins.split(",") if o.strip()]
)
if settings.debug:
    _CORS_ORIGINS = ["http://localhost:5173", "http://localhost:3000", "http://localhost:6001"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials="*" not in _CORS_ORIGINS,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(self)"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-XSS-Protection"] = "0"
        return response


app.add_middleware(SecurityHeadersMiddleware)

app.include_router(map.router, prefix="/api")
app.include_router(venue.router, prefix="/api")
app.include_router(tournament.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(sheets.router, prefix="/api")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


# StaticFiles は最後にマウント（API ルートより後にマウントすると上書きされる）
_UI_DIST = Path(__file__).parent.parent.parent / "ui" / "dist"
if _UI_DIST.exists():
    app.mount("/", StaticFiles(directory=_UI_DIST, html=True), name="ui")
