"""GET /venues/ 店舗一覧 / GET /venue/{id} 店舗詳細"""

import uuid
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import extract, func, inspect, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from tas.api.limiter import limiter
from tas.config import settings
from tas.api.schemas import (
    ReportCreate,
    ReportResponse,
    TournamentBrief,
    VenueCard,
    VenueDetail,
    VenueListResponse,
)
from tas.constants import JACK_MAX_BUYIN, QUEEN_MAX_BUYIN, NEAR_MAX_DISTANCE_DEG_SQ
from tas.db.models import Report, Tournament, Venue
from tas.db.session import get_session

router = APIRouter(tags=["venue"])


@router.get("/venues/", response_model=VenueListResponse)
@limiter.limit(settings.rate_limit_default)
async def list_venues(
    request: Request,
    prefecture: Optional[List[str]] = Query(None, description="都道府県で絞り込み（複数可, 例: 東京都）"),
    open_status: Optional[Literal["open", "preparing", "closed", "unknown"]] = Query(None, description="open / preparing / closed / unknown"),
    has_price: Optional[bool] = Query(None, description="料金情報ありのみ"),
    has_tournament: Optional[bool] = Query(None, description="大会情報ありのみ"),
    tournament_month_from: Optional[int] = Query(None, ge=1, le=12, description="大会開催月（開始, 1〜12）"),
    tournament_month_to: Optional[int] = Query(None, ge=1, le=12, description="大会開催月（終了, 1〜12）"),
    jack_tournament: Optional[bool] = Query(None, description="バイイン 1,000円以下の大会あり"),
    queen_tournament: Optional[bool] = Query(None, description="バイイン 3,000円以下の大会あり"),
    king_tournament: Optional[bool] = Query(None, description="賞金保証ありの大会あり"),
    food_level: Optional[Literal["none", "basic", "rich"]] = Query(None, description="フードレベル (none/basic/rich)"),
    min_tables: Optional[int] = Query(None, ge=1, description="最低テーブル数"),
    drink_rich: Optional[bool] = Query(None, description="ドリンク充実のみ"),
    sort: Literal["updated", "name", "near"] = Query("updated", description="updated / name / near"),
    user_lat: Optional[float] = Query(None, description="現在地の緯度（sort=near 時に使用）"),
    user_lng: Optional[float] = Query(None, description="現在地の経度（sort=near 時に使用）"),
    offset: int = Query(0, ge=0),
    limit: int = Query(30, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> VenueListResponse:
    base = select(Venue).where(Venue.visibility_status == "visible")

    if prefecture:
        prefs_ext = []
        for p in prefecture:
            prefs_ext.append(p)
            if p != "北海道" and p.endswith(("都", "府", "県")):
                prefs_ext.append(p[:-1])
        base = base.where(Venue.area_prefecture.in_(prefs_ext))
    if open_status:
        base = base.where(Venue.open_status == open_status)
    if has_price:
        base = base.where(Venue.price_entry_min.is_not(None))

    if food_level:
        base = base.where(Venue.food_level == food_level)
    if min_tables is not None:
        base = base.where(Venue.table_count >= min_tables)
    if drink_rich:
        base = base.where(Venue.drink_required == True)  # noqa: E712

    # 大会月フィルタ（年またぎ対応）
    if tournament_month_from is not None or tournament_month_to is not None:
        t_month_subq = select(Tournament.venue_id).distinct().where(
            Tournament.status == "scheduled",
            Tournament.start_at.is_not(None),
        )
        m_from = tournament_month_from
        m_to = tournament_month_to
        month_col = extract("month", Tournament.start_at)
        if m_from is not None and m_to is not None and m_from > m_to:
            # 年またぎ: 例 11月〜2月 → month >= 11 OR month <= 2
            t_month_subq = t_month_subq.where(
                or_(month_col >= m_from, month_col <= m_to)
            )
        else:
            if m_from is not None:
                t_month_subq = t_month_subq.where(month_col >= m_from)
            if m_to is not None:
                t_month_subq = t_month_subq.where(month_col <= m_to)
        base = base.where(Venue.id.in_(t_month_subq))

    # J/Q/K バイイン大会フィルタ
    jqk_conditions = []
    if jack_tournament:
        jqk_conditions.append(
            Venue.id.in_(
                select(Tournament.venue_id).distinct().where(
                    Tournament.status == "scheduled",
                    Tournament.buy_in.is_not(None),
                    Tournament.buy_in <= JACK_MAX_BUYIN,
                )
            )
        )
    if queen_tournament:
        jqk_conditions.append(
            Venue.id.in_(
                select(Tournament.venue_id).distinct().where(
                    Tournament.status == "scheduled",
                    Tournament.buy_in.is_not(None),
                    Tournament.buy_in <= QUEEN_MAX_BUYIN,
                )
            )
        )
    if king_tournament:
        jqk_conditions.append(
            Venue.id.in_(
                select(Tournament.venue_id).distinct().where(
                    Tournament.status == "scheduled",
                    Tournament.guarantee.is_not(None),
                    Tournament.guarantee > 0,
                )
            )
        )
    if jqk_conditions:
        base = base.where(or_(*jqk_conditions))

    # has_tournament フィルタ: tournamentsサブクエリ
    if has_tournament is not None:
        subq = select(Tournament.venue_id).distinct().subquery()
        if has_tournament:
            base = base.where(Venue.id.in_(select(subq.c.venue_id)))
        else:
            base = base.where(Venue.id.not_in(select(subq.c.venue_id)))

    # 件数カウント
    count_query = select(func.count()).select_from(base.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar_one()

    # ソート
    if sort == "name":
        base = base.order_by(Venue.name.asc())
    elif sort == "near" and user_lat is not None and user_lng is not None:
        # 距離の二乗（近似）で昇順ソート。約50km以内に絞り込み
        dist_expr = (
            (Venue.lat - user_lat) * (Venue.lat - user_lat)
            + (Venue.lng - user_lng) * (Venue.lng - user_lng)
        )
        max_dist_sq = NEAR_MAX_DISTANCE_DEG_SQ
        base = base.where(Venue.lat.is_not(None), dist_expr <= max_dist_sq)
        base = base.order_by(dist_expr.asc())
    else:
        # デフォルト: 更新日時の新しい順
        base = base.order_by(Venue.updated_at.desc())

    base = base.offset(offset).limit(limit)
    result = await session.execute(base)
    venues = result.scalars().all()

    # 各店舗の直近大会を一括取得
    venue_ids = [v.id for v in venues]
    next_tournaments: dict[str, Tournament] = {}
    if venue_ids:
        t_query = (
            select(Tournament)
            .where(
                Tournament.venue_id.in_(venue_ids),
                Tournament.status == "scheduled",
            )
            .order_by(Tournament.start_at.asc())
            .limit(2000)
        )
        t_result = await session.execute(t_query)
        for t in t_result.scalars():
            if t.venue_id not in next_tournaments:
                next_tournaments[t.venue_id] = t

    items: list[VenueCard] = []
    for venue in venues:
        nt = next_tournaments.get(venue.id)
        card = VenueCard.model_validate(venue)
        card.next_tournament_title = nt.title if nt else None
        card.next_tournament_start = nt.start_at if nt else None
        card.next_tournament_url = nt.url if nt and nt.url else None
        items.append(card)

    return VenueListResponse(items=items, total=total, offset=offset, limit=limit)


@router.get("/venue/{venue_id}", response_model=VenueDetail)
@limiter.limit(settings.rate_limit_default)
async def get_venue(
    request: Request,
    venue_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> VenueDetail:
    result = await session.execute(
        select(Venue).where(
            Venue.id == str(venue_id),
            Venue.visibility_status == "visible",
        )
    )
    venue = result.scalar_one_or_none()
    if venue is None:
        raise HTTPException(status_code=404, detail="Venue not found")

    # 大会一覧（直近順）
    tournaments_result = await session.execute(
        select(Tournament)
        .where(Tournament.venue_id == str(venue_id))
        .order_by(Tournament.start_at.asc())
        .limit(200)
    )
    tournaments = [TournamentBrief.model_validate(t) for t in tournaments_result.scalars()]

    # ORMオブジェクトをカラム属性のみのdictに変換し、lazyロードを回避
    mapper = inspect(type(venue))
    venue_dict = {c.key: getattr(venue, c.key) for c in mapper.column_attrs}
    venue_dict['tournaments'] = tournaments
    detail = VenueDetail.model_validate(venue_dict)
    return detail


@router.post("/venue/{venue_id}/report", response_model=ReportResponse, status_code=201)
@limiter.limit(settings.rate_limit_report)
async def report_venue(
    request: Request,  # Required by slowapi
    venue_id: uuid.UUID,
    body: ReportCreate,
    session: AsyncSession = Depends(get_session),
) -> ReportResponse:
    result = await session.execute(
        select(Venue).where(Venue.id == str(venue_id))
    )
    venue = result.scalar_one_or_none()
    if venue is None:
        raise HTTPException(status_code=404, detail="Venue not found")

    report = Report(
        report_type=body.report_type,
        entity_type="venue",
        entity_id=str(venue_id),
        reporter_name=body.reporter_name,
        reporter_contact=body.reporter_contact,
        details=body.details,
        status="pending",
    )
    session.add(report)
    await session.flush()
    await session.refresh(report)
    return ReportResponse.model_validate(report)
