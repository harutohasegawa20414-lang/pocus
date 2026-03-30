"""GET /tournaments — 大会一覧"""

import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tas.api.schemas import TournamentBrief
from tas.db.models import Tournament, Venue
from tas.db.session import get_session

router = APIRouter(prefix="/tournaments", tags=["tournaments"])


@router.get("/", response_model=list[TournamentBrief])
async def list_tournaments(
    venue_id: Optional[uuid.UUID] = Query(None, description="店舗IDで絞り込み"),
    status: Optional[Literal["scheduled", "canceled", "finished", "unknown"]] = Query(
        None, description="ステータスで絞り込み"
    ),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[TournamentBrief]:
    # 公開中の店舗に紐づく大会のみ返す
    visible_venue_ids = select(Venue.id).where(Venue.visibility_status == "visible")
    query = select(Tournament).where(
        Tournament.venue_id.in_(visible_venue_ids)
    ).order_by(Tournament.start_at.asc())

    if venue_id:
        query = query.where(Tournament.venue_id == str(venue_id))
    if status:
        query = query.where(Tournament.status == status)

    query = query.limit(limit)
    result = await session.execute(query)
    return [TournamentBrief.model_validate(t) for t in result.scalars()]
