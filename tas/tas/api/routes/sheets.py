"""Google Sheets エクスポート API"""

import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tas.api.auth import require_admin
from tas.db.models import Venue
from tas.db.session import get_session
from tas import sheets as sheets_svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sheets", tags=["sheets"], dependencies=[Depends(require_admin)])


class WriteRequest(BaseModel):
    sheet_name: str = Field("Sheet1", max_length=100, pattern=r"^[\w\s\-]+$")
    rows: list[list[Any]] = Field(max_length=10000)
    mode: Literal["append", "overwrite"] = "append"


class WriteResponse(BaseModel):
    updated_rows: int
    sheet_name: str


@router.post("/write", response_model=WriteResponse)
async def write_rows(body: WriteRequest) -> WriteResponse:
    """任意の行データをスプレッドシートに書き込む。"""
    try:
        if body.mode == "overwrite":
            count = sheets_svc.clear_and_write(body.sheet_name, body.rows)
        else:
            count = sheets_svc.append_rows(body.sheet_name, body.rows)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("[sheets/write] %s", e, exc_info=True)
        raise HTTPException(status_code=502, detail="Google Sheets への書き込みに失敗しました")
    return WriteResponse(updated_rows=count, sheet_name=body.sheet_name)


@router.post("/export/venues", response_model=WriteResponse)
async def export_venues(
    sheet_name: str = Query("Venues", max_length=100, pattern=r"^[\w\s\-]+$"),
    session: AsyncSession = Depends(get_session),
) -> WriteResponse:
    """DBの店舗データをスプレッドシートに書き出す（上書きモード）。"""
    result = await session.execute(
        select(Venue).where(Venue.visibility_status == "visible").order_by(Venue.name).limit(10000)
    )
    venues = result.scalars().all()

    header = [
        "ID", "名前", "都道府県", "市区町村", "住所", "緯度", "経度",
        "入場料(最小)", "入場料メモ", "テーブル数", "最終更新",
    ]
    rows: list[list[Any]] = [header]
    for v in venues:
        rows.append([
            str(v.id),
            v.name or "",
            v.area_prefecture or "",
            v.area_city or "",
            v.address or "",
            float(v.lat) if v.lat is not None else "",
            float(v.lng) if v.lng is not None else "",
            v.price_entry_min if v.price_entry_min is not None else "",
            v.price_note or "",
            v.table_count if v.table_count is not None else "",
            v.last_updated_at.isoformat() if v.last_updated_at else "",
        ])

    try:
        count = sheets_svc.clear_and_write(sheet_name, rows)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("[sheets/export/venues] %s", e, exc_info=True)
        raise HTTPException(status_code=502, detail="Google Sheets への書き込みに失敗しました")

    return WriteResponse(updated_rows=count, sheet_name=sheet_name)
