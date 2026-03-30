"""CLIエントリポイント（crawl/seed/server）"""

import asyncio
import logging
import uuid as _uuid
from typing import Optional

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.markup import escape as rich_escape

app = typer.Typer(name="tas", help="POCUS - ポーカー店舗情報集約システム")
console = Console()

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(console=console, show_time=False, show_path=False)],
)


@app.command()
def server(
    host: str = typer.Option(None, help="APIホスト"),
    port: int = typer.Option(None, help="APIポート"),
    reload: bool = typer.Option(False, help="開発用ホットリロード"),
) -> None:
    """FastAPI サーバーを起動する"""
    import uvicorn

    from tas.config import settings

    uvicorn.run(
        "tas.api.main:app",
        host=host or settings.api_host,
        port=port or settings.api_port,
        reload=reload,
        log_level="debug" if settings.debug else "info",
    )


@app.command()
def crawl(
    limit: int = typer.Option(10, help="クロールするURL数の上限"),
    dry_run: bool = typer.Option(False, help="DBへの書き込みなし（テスト用）"),
    source_id: Optional[str] = typer.Option(None, help="特定ソースIDのみ実行（UUID形式）"),
) -> None:
    """pendingソースをクロールする"""
    # source_id のUUID形式バリデーション
    if source_id is not None:
        try:
            _uuid.UUID(source_id)
        except ValueError:
            console.print(f"[red]source_id は UUID 形式で指定してください: {rich_escape(source_id)}[/red]")
            raise typer.Exit(1)

    async def _run() -> None:
        from tas.crawler.engine import CrawlEngine
        from tas.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            engine = CrawlEngine(session=session, dry_run=dry_run)
            count = await engine.run(limit=limit, source_id=source_id)
            console.print(f"[green]クロール完了: {count} 件処理[/green]")

    asyncio.run(_run())


@app.command()
def seed(
    url: Optional[str] = typer.Option(None, help="手動でURLをsourcesに追加"),
    from_sheets: bool = typer.Option(False, help="Google Sheetsから読み込む"),
    from_file: Optional[str] = typer.Option(None, help="CSVファイルから一括インポート"),
    seed_type: str = typer.Option("manual", help="シードタイプ"),
    priority: int = typer.Option(5, min=1, max=10, help="優先度（1-10）"),
) -> None:
    """ソースURLを追加する"""

    async def _run() -> None:
        from tas.db.models import Source
        from tas.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            if url:
                from sqlalchemy import select

                existing = await session.execute(
                    select(Source).where(Source.seed_url == url)
                )
                if existing.scalar_one_or_none():
                    console.print(f"[yellow]既に存在します: {url}[/yellow]")
                    return

                source = Source(
                    seed_url=url,
                    seed_type=seed_type,
                    priority=priority,
                    status="pending",
                )
                session.add(source)
                await session.commit()
                console.print(f"[green]追加しました: {url}[/green]")

            if from_file:
                added = await _import_csv(session, from_file)
                console.print(f"[green]{from_file} から {added} 件追加しました[/green]")

            if from_sheets:
                from tas.seeds.sheets import SheetsClient

                client = SheetsClient()
                added = await client.sync_to_db(session)
                console.print(f"[green]Sheetsから {added} 件追加しました[/green]")

    asyncio.run(_run())


async def _import_csv(session, filepath: str) -> int:
    """
    CSVファイルからSourceを一括インポートする。
    必須列: seed_url
    任意列: seed_type, region_hint, priority, page_kind, owner, source_name, note
    """
    import csv

    from sqlalchemy import select

    from tas.db.models import Source

    added = 0
    with open(filepath, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = (row.get("seed_url") or "").strip()
            if not url or url.startswith("#"):
                continue

            existing = await session.execute(
                select(Source).where(Source.seed_url == url)
            )
            if existing.scalar_one_or_none():
                continue

            try:
                prio = int(row.get("priority") or 5)
            except ValueError:
                prio = 5
            prio = max(1, min(10, prio))

            source = Source(
                seed_url=url,
                seed_type=(row.get("seed_type") or "manual").strip(),
                region_hint=(row.get("region_hint") or "").strip() or None,
                priority=prio,
                page_kind=(row.get("page_kind") or "").strip() or None,
                owner=(row.get("owner") or "").strip() or None,
                source_name=(row.get("source_name") or "").strip() or None,
                note=(row.get("note") or "").strip() or None,
                status="pending",
            )
            session.add(source)
            added += 1

    if added:
        await session.commit()
    return added


@app.command()
def discover(
    mode: str = typer.Argument(
        "all", help="実行モード: all / directories / search"
    ),
    prefectures: Optional[str] = typer.Option(
        None, help="検索対象の都道府県（カンマ区切り、例: 東京都,大阪府）"
    ),
    dry_run: bool = typer.Option(False, help="DB書き込みなし（テスト用）"),
) -> None:
    """新店舗を自動発見する（ディレクトリ登録 + Web検索）"""

    async def _run() -> None:
        from tas.crawler.web_search import search_discover, seed_directory_sources
        from tas.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            if mode in ("all", "directories"):
                count = await seed_directory_sources(session, dry_run=dry_run)
                console.print(
                    f"[green]ディレクトリ: {count} 件{'登録予定' if dry_run else '登録完了'}[/green]"
                )

            if mode in ("all", "search"):
                pref_list = None
                if prefectures:
                    pref_list = [p.strip() for p in prefectures.split(",") if p.strip()]
                count = await search_discover(
                    session, prefectures=pref_list, dry_run=dry_run
                )
                console.print(
                    f"[green]Web検索: {count} 件{'発見予定' if dry_run else '登録完了'}[/green]"
                )

    asyncio.run(_run())


@app.command()
def fixtures(
    reset: bool = typer.Option(False, help="既存の開発フィクスチャを削除してから再投入する"),
) -> None:
    """開発用テストフィクスチャを DB に投入する（seeds/fixtures.json）"""

    async def _run() -> None:
        import json
        from datetime import datetime, timezone
        from pathlib import Path

        from sqlalchemy import select

        from tas.db.models import Source, Tournament, Venue
        from tas.db.session import AsyncSessionLocal

        fixtures_path = Path(__file__).parent.parent / "seeds" / "fixtures.json"
        if not fixtures_path.exists():
            console.print(f"[red]fixtures.json が見つかりません: {fixtures_path}[/red]")
            raise typer.Exit(1)

        data = json.loads(fixtures_path.read_text(encoding="utf-8"))

        async with AsyncSessionLocal() as session:
            if reset:
                # 既存データをすべて削除してクリーンにする
                await session.execute(__import__("sqlalchemy").delete(Tournament))
                await session.execute(__import__("sqlalchemy").delete(Venue))
                await session.execute(__import__("sqlalchemy").delete(Source))
                await session.commit()
                console.print("[yellow]既存の店舗・大会・ソースデータをすべて削除しました[/yellow]")

            # Sources を投入
            source_added = 0
            for s_data in data.get("sources", []):
                existing = await session.scalar(
                    select(Source).where(Source.seed_url == s_data["seed_url"])
                )
                if existing:
                    continue
                session.add(Source(**{k: v for k, v in s_data.items()}, status="pending"))
                source_added += 1

            # Venues + Tournaments を投入
            venue_added = 0
            tournament_added = 0
            for v_data in data.get("venues", []):
                tournaments_data = v_data.pop("tournaments", [])
                existing = await session.scalar(
                    select(Venue).where(Venue.name == v_data["name"])
                )
                if existing:
                    continue
                venue = Venue(**v_data)
                session.add(venue)
                await session.flush()  # ID 確定
                venue_added += 1

                for t_data in tournaments_data:
                    start_raw = t_data.get("start_at")
                    start_at = (
                        datetime.fromisoformat(start_raw) if start_raw else None
                    )
                    session.add(Tournament(
                        venue_id=venue.id,
                        title=t_data["title"],
                        start_at=start_at,
                        buy_in=t_data.get("buy_in"),
                        guarantee=t_data.get("guarantee"),
                        capacity=t_data.get("capacity"),
                        url=t_data.get("url", ""),
                        status=t_data.get("status", "scheduled"),
                        last_updated_at=datetime.now(timezone.utc),
                    ))
                    tournament_added += 1

            await session.commit()
            console.print(
                f"[green]フィクスチャ投入完了: "
                f"sources={source_added}, venues={venue_added}, "
                f"tournaments={tournament_added}[/green]"
            )

    asyncio.run(_run())


@app.command()
def migrate() -> None:
    """Alembicマイグレーションを実行する（upgrade head）"""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=False,
    )
    raise typer.Exit(result.returncode)


@app.command()
def stats() -> None:
    """DB統計を表示する"""

    async def _run() -> None:
        from sqlalchemy import func, select

        from tas.db.models import CrawlLog, Report, Source, Tournament, Venue
        from tas.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            venue_count = await session.scalar(select(func.count(Venue.id)))
            tournament_count = await session.scalar(select(func.count(Tournament.id)))
            source_count = await session.scalar(select(func.count(Source.id)))
            log_count = await session.scalar(select(func.count(CrawlLog.id)))
            report_count = await session.scalar(select(func.count(Report.id)))

            console.print("\n[bold]POCUS データベース統計[/bold]")
            console.print(f"  Venues     : {venue_count:,}")
            console.print(f"  Tournaments: {tournament_count:,}")
            console.print(f"  Sources    : {source_count:,}")
            console.print(f"  CrawlLogs  : {log_count:,}")
            console.print(f"  Reports    : {report_count:,}\n")

    asyncio.run(_run())


@app.command()
def clean(
    skip_domain: Optional[str] = typer.Option(
        None, help="指定ドメインのSourceをすべてskipにする（例: tattoo-navi.jp）"
    ),
    skip_errors: bool = typer.Option(
        False, help="fail_count>=3のエラーSourceをskipにする"
    ),
    reset_pending: bool = typer.Option(
        False, help="done/errorのSourceをpendingに戻す（再クロール）"
    ),
    dry_run: bool = typer.Option(False, help="変更内容を表示するだけ（DB書き込みなし）"),
) -> None:
    """Sourceのステータスを一括管理する"""

    async def _run() -> None:
        from urllib.parse import urlparse

        from sqlalchemy import update

        from tas.db.models import Source
        from tas.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            total = 0

            if skip_domain:
                result = await session.execute(
                    __import__("sqlalchemy", fromlist=["select"])
                    .select(Source)
                    .where(Source.status != "skip")
                )
                targets = [
                    s for s in result.scalars().all()
                    if urlparse(s.seed_url).netloc == skip_domain
                    or urlparse(s.seed_url).netloc.endswith(f".{skip_domain}")
                ]
                for s in targets:
                    if dry_run:
                        console.print(f"  [dim]SKIP: {s.seed_url}[/dim]")
                    else:
                        s.status = "skip"
                    total += 1
                console.print(
                    f"[{'yellow' if dry_run else 'green'}]"
                    f"{skip_domain}: {total} 件を{'skip予定' if dry_run else 'skipに変更'}[/]"
                )

            if skip_errors:
                from sqlalchemy import select
                result = await session.execute(
                    select(Source).where(
                        Source.status == "error",
                        Source.fail_count >= 3,
                    )
                )
                targets = result.scalars().all()
                for s in targets:
                    if dry_run:
                        console.print(f"  [dim]SKIP: {s.seed_url} (fail={s.fail_count})[/dim]")
                    else:
                        s.status = "skip"
                    total += 1
                console.print(
                    f"[{'yellow' if dry_run else 'green'}]"
                    f"エラーSource: {total} 件を{'skip予定' if dry_run else 'skipに変更'}[/]"
                )

            if reset_pending:
                from sqlalchemy import select
                result = await session.execute(
                    select(Source).where(Source.status.in_(["done", "error", "running"]))
                )
                targets = result.scalars().all()
                count = 0
                for s in targets:
                    if dry_run:
                        console.print(f"  [dim]RESET: {s.seed_url} ({s.status}→pending)[/dim]")
                    else:
                        s.status = "pending"
                        s.fail_count = 0
                        s.error_reason = None
                    count += 1
                console.print(
                    f"[{'yellow' if dry_run else 'green'}]"
                    f"{count} 件を{'pending予定' if dry_run else 'pendingにリセット'}[/]"
                )

            if not dry_run:
                await session.commit()

    asyncio.run(_run())


@app.command()
def review(
    revert_auto: bool = typer.Option(
        False, help="自動発見でvisibleになった店舗をpending_reviewに戻す"
    ),
    dry_run: bool = typer.Option(False, help="変更内容を表示するだけ（DB書き込みなし）"),
) -> None:
    """自動発見された店舗のレビューステータスを管理する"""

    async def _run() -> None:
        from sqlalchemy import select

        from tas.db.models import Source, Venue
        from tas.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            if revert_auto:
                # 自動発見（manual/sheets以外）のSourceに紐づくvisible店舗を探す
                auto_types = ("web_search", "venue_official", "directory")
                auto_sources = await session.execute(
                    select(Source.seed_url).where(
                        Source.seed_type.in_(auto_types)
                    )
                )
                auto_urls = {row[0] for row in auto_sources}

                if not auto_urls:
                    console.print("[yellow]自動発見のSourceが見つかりません[/yellow]")
                    return

                result = await session.execute(
                    select(Venue).where(
                        Venue.visibility_status == "visible",
                        Venue.verification_status == "unverified",
                    )
                )
                count = 0
                for venue in result.scalars():
                    # website_urlまたはsources配列が自動発見URLと一致するか
                    venue_urls = set(venue.sources or [])
                    if venue.website_url:
                        venue_urls.add(venue.website_url)
                    if venue_urls & auto_urls:
                        if dry_run:
                            console.print(
                                f"  [dim]REVERT: {venue.name} ({venue.area_prefecture or '—'})[/dim]"
                            )
                        else:
                            venue.visibility_status = "pending_review"
                        count += 1

                if not dry_run and count > 0:
                    await session.commit()

                label = "戻す予定" if dry_run else "pending_reviewに戻しました"
                console.print(
                    f"[{'yellow' if dry_run else 'green'}]{count} 件を{label}[/]"
                )
            else:
                # オプション未指定時は現在のレビュー状態を表示
                from sqlalchemy import func

                for status in ("pending_review", "visible", "hidden"):
                    cnt = await session.scalar(
                        select(func.count(Venue.id)).where(
                            Venue.visibility_status == status
                        )
                    )
                    console.print(f"  {status:20s}: {cnt:,} 件")

    asyncio.run(_run())


if __name__ == "__main__":
    app()
