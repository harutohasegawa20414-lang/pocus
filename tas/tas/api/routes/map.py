"""GET /map/pins — 店舗ピン取得"""

from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, extract, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from tas.api.limiter import limiter
from tas.config import settings
from tas.api.schemas import VenuePin, VenuePinsResponse
from tas.constants import JACK_MAX_BUYIN, QUEEN_MAX_BUYIN, NEAR_MAX_DISTANCE_DEG_SQ
from tas.db.models import Tournament, Venue
from tas.db.session import get_session

router = APIRouter(prefix="/map", tags=["map"])


@router.get("/pins", response_model=VenuePinsResponse)
@limiter.limit(settings.rate_limit_default)
async def get_map_pins(
    request: Request,
    bbox: Optional[str] = Query(
        None,
        description="西経,南緯,東経,北緯 (例: 130,31,141,46)",
    ),
    prefecture: Optional[List[str]] = Query(None, description="都道府県（複数可）"),
    open_now: Optional[bool] = Query(None, description="営業中のみ"),
    has_tournament: Optional[bool] = Query(None, description="今日大会ありのみ"),
    has_price: Optional[bool] = Query(None, description="料金情報ありのみ"),
    tournament_month_from: Optional[int] = Query(None, ge=1, le=12),
    tournament_month_to: Optional[int] = Query(None, ge=1, le=12),
    jack_tournament: Optional[bool] = Query(None, description="バイイン 1,000円以下の大会あり"),
    queen_tournament: Optional[bool] = Query(None, description="バイイン 3,000円以下の大会あり"),
    king_tournament: Optional[bool] = Query(None, description="賞金保証ありの大会あり"),
    food_level: Optional[Literal["none", "basic", "rich"]] = Query(None, description="フードレベル (none/basic/rich)"),
    min_tables: Optional[int] = Query(None, ge=1),
    drink_rich: Optional[bool] = Query(None, description="ドリンク充実のみ"),
    zoom: Optional[int] = Query(None, ge=1, le=20, description="マップズームレベル（将来のクラスタリング用）"),
    user_lat: Optional[float] = Query(None, description="現在地の緯度（近い順ソート用）"),
    user_lng: Optional[float] = Query(None, description="現在地の経度（近い順ソート用）"),
    limit: int = Query(500, ge=1, le=2000),
    session: AsyncSession = Depends(get_session),
) -> VenuePinsResponse:
    # bboxパース
    min_lng, min_lat, max_lng, max_lat = None, None, None, None
    if bbox:
        parts = bbox.split(",")
        if len(parts) == 4:
            try:
                min_lng, min_lat, max_lng, max_lat = (float(p) for p in parts)
            except ValueError:
                pass

    query = select(Venue).where(
        Venue.visibility_status == "visible",
        Venue.lat.is_not(None),
        Venue.lng.is_not(None),
    )

    if min_lat is not None:
        query = query.where(
            and_(
                Venue.lat >= min_lat,
                Venue.lat <= max_lat,
                Venue.lng >= min_lng,
                Venue.lng <= max_lng,
            )
        )
    if prefecture:
        prefs_ext = []
        for p in prefecture:
            prefs_ext.append(p)
            if p != "北海道" and p.endswith(("都", "府", "県")):
                prefs_ext.append(p[:-1])
        query = query.where(Venue.area_prefecture.in_(prefs_ext))
    if open_now:
        query = query.where(Venue.open_status == "open")
    if has_price:
        query = query.where(Venue.price_entry_min.is_not(None))
    if food_level:
        query = query.where(Venue.food_level == food_level)
    if min_tables is not None:
        query = query.where(Venue.table_count >= min_tables)
    if drink_rich:
        query = query.where(Venue.drink_required == True)  # noqa: E712
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
        query = query.where(Venue.id.in_(t_month_subq))

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
        query = query.where(or_(*jqk_conditions))

    # ソート: 現在地指定ありなら近い順（50km以内に絞り込み）、なければ更新日時の新しい順
    if user_lat is not None and user_lng is not None:
        dist_expr = (
            (Venue.lat - user_lat) * (Venue.lat - user_lat)
            + (Venue.lng - user_lng) * (Venue.lng - user_lng)
        )
        max_dist_sq = NEAR_MAX_DISTANCE_DEG_SQ
        query = query.where(dist_expr <= max_dist_sq)
        query = query.order_by(dist_expr.asc())
    else:
        query = query.order_by(Venue.updated_at.desc())

    query = query.limit(limit)
    result = await session.execute(query)
    venues = result.scalars().all()

    # 大会フィルタ＆次回大会取得
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

    pins: list[VenuePin] = []
    for venue in venues:
        if has_tournament and venue.id not in next_tournaments:
            continue
        nt = next_tournaments.get(venue.id)
        pins.append(
            VenuePin(
                id=venue.id,
                type="venue",
                lat=float(venue.lat),
                lng=float(venue.lng),
                display_name=venue.name,
                open_status=venue.open_status,
                hours_today=venue.hours_today,
                price_entry_min=venue.price_entry_min,
                next_tournament_title=nt.title if nt else None,
                next_tournament_start=nt.start_at if nt else None,
                area_prefecture=venue.area_prefecture,
                area_city=venue.area_city,
                verification_status=venue.verification_status,
                detail_url=f"/venues/{venue.id}",
                booking_url=None,
                food_level=venue.food_level,
                table_count=venue.table_count,
                drink_required=venue.drink_required,
            )
        )

    return VenuePinsResponse(pins=pins, total=len(pins))
