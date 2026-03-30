"""管理者ダッシュボード API（POCUS）"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tas.api.auth import require_admin
from tas.api.limiter import limiter
from tas.api.schemas import (
    AdminStats,
    CrawlResetStaleResponse,
    CrawlTriggerResponse,
    DiscoveryBulkReviewRequest,
    DiscoveryReviewRequest,
    DiscoveryTriggerResponse,
    DiscoveryVenueItem,
    MergeCandidateItem,
    MergeCandidateResolve,
    RecentEntry,
    ReportResolve,
    ReportResponse,
    SchedulerStatus,
    SourceItem,
    VenueCard,
)
from tas.config import settings
from tas.constants import LOW_CONFIDENCE_THRESHOLD, STALE_VENUES_LIMIT
from tas.db.models import CrawlLog, Report, ReportHistory, Source, Tournament, Venue, VenueMergeCandidate
from tas.db.session import get_session

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin", tags=["admin"],
    dependencies=[Depends(require_admin)],
)

_ADMIN_RATE_LIMIT = "30/minute"

_STALE_VENUES_LIMIT = STALE_VENUES_LIMIT


@router.get("/stats", response_model=AdminStats)
async def get_stats(
    session: AsyncSession = Depends(get_session),
) -> AdminStats:
    total_venues = await session.scalar(select(func.count(Venue.id))) or 0
    total_tournaments = await session.scalar(select(func.count(Tournament.id))) or 0
    total_sources = await session.scalar(select(func.count(Source.id))) or 0
    pending_sources = (
        await session.scalar(
            select(func.count(Source.id)).where(Source.status == "pending")
        )
        or 0
    )
    error_sources = (
        await session.scalar(
            select(func.count(Source.id)).where(Source.status == "error")
        )
        or 0
    )
    done_sources = (
        await session.scalar(
            select(func.count(Source.id)).where(Source.status == "done")
        )
        or 0
    )
    running_sources = (
        await session.scalar(
            select(func.count(Source.id)).where(Source.status == "running")
        )
        or 0
    )
    total_crawl_logs = await session.scalar(select(func.count(CrawlLog.id))) or 0
    low_confidence_venues = (
        await session.scalar(
            select(func.count(Venue.id)).where(Venue.match_confidence < LOW_CONFIDENCE_THRESHOLD)
        )
        or 0
    )
    pending_reports = (
        await session.scalar(
            select(func.count(Report.id)).where(Report.status == "pending")
        )
        or 0
    )
    disabled_sources = (
        await session.scalar(
            select(func.count(Source.id)).where(Source.status == "disabled")
        )
        or 0
    )
    blocked_suspected_sources = (
        await session.scalar(
            select(func.count(Source.id)).where(Source.error_reason == "blocked_suspected")
        )
        or 0
    )
    pending_merge_candidates = (
        await session.scalar(
            select(func.count(VenueMergeCandidate.id)).where(
                VenueMergeCandidate.status == "pending"
            )
        )
        or 0
    )

    return AdminStats(
        total_venues=total_venues,
        total_tournaments=total_tournaments,
        total_sources=total_sources,
        pending_sources=pending_sources,
        running_sources=running_sources,
        error_sources=error_sources,
        done_sources=done_sources,
        disabled_sources=disabled_sources,
        blocked_suspected_sources=blocked_suspected_sources,
        total_crawl_logs=total_crawl_logs,
        low_confidence_venues=low_confidence_venues,
        pending_reports=pending_reports,
        pending_merge_candidates=pending_merge_candidates,
    )


@router.get("/recent", response_model=list[RecentEntry])
async def get_recent(
    limit: int = Query(30, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[RecentEntry]:
    """最近追加された店舗（新しい順）"""
    venues = await session.execute(
        select(Venue).where(Venue.visibility_status == "visible")
        .order_by(Venue.created_at.desc()).limit(limit)
    )

    entries = []
    for v in venues.scalars():
        entries.append(RecentEntry(
            id=v.id, name=v.name, type="venue",
            area_prefecture=v.area_prefecture, area_city=v.area_city,
            match_confidence=float(v.match_confidence) if v.match_confidence else None,
            created_at=v.created_at,
        ))

    entries.sort(key=lambda e: e.created_at, reverse=True)
    return entries[:limit]


@router.get("/sources", response_model=list[SourceItem])
async def get_sources(
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[SourceItem]:
    """ソース一覧"""
    result = await session.execute(
        select(Source).order_by(Source.status, Source.created_at.desc())
        .limit(limit).offset(offset)
    )
    return [SourceItem.model_validate(s) for s in result.scalars()]


@router.get("/reports", response_model=list[ReportResponse])
async def get_reports(
    status: Literal["pending", "resolved", "rejected"] | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[ReportResponse]:
    """レポート一覧"""
    query = select(Report).order_by(Report.created_at.desc())
    if status:
        query = query.where(Report.status == status)
    query = query.limit(limit).offset(offset)
    result = await session.execute(query)
    return [ReportResponse.model_validate(r) for r in result.scalars()]


@router.get("/merge-candidates", response_model=list[MergeCandidateItem])
async def get_merge_candidates(
    status: Literal["pending", "merged", "rejected"] | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[MergeCandidateItem]:
    """統合候補一覧（pending / merged / rejected）"""
    query = select(VenueMergeCandidate).order_by(VenueMergeCandidate.created_at.desc())
    if status:
        query = query.where(VenueMergeCandidate.status == status)
    query = query.limit(limit).offset(offset)
    result = await session.execute(query)
    return [MergeCandidateItem.model_validate(mc) for mc in result.scalars()]


@router.patch("/merge-candidates/{candidate_id}", response_model=MergeCandidateItem, status_code=200)
@limiter.limit(_ADMIN_RATE_LIMIT)
async def resolve_merge_candidate(
    request: Request,
    candidate_id: uuid.UUID,
    body: MergeCandidateResolve,
    session: AsyncSession = Depends(get_session),
) -> MergeCandidateItem:
    """
    統合候補を処理する。
    - action=merged: venue_b の情報を venue_a にマージし venue_b を非表示にする
    - action=rejected: 候補を却下する（データは変更しない）
    """
    result = await session.execute(
        select(VenueMergeCandidate).where(VenueMergeCandidate.id == str(candidate_id))
    )
    candidate = result.scalar_one_or_none()
    if candidate is None:
        raise HTTPException(status_code=404, detail="Merge candidate not found")
    if candidate.status != "pending":
        raise HTTPException(status_code=409, detail=f"Candidate is already {candidate.status}")

    now = datetime.now(timezone.utc)

    if body.action == "merged":
        venue_a = await session.get(Venue, candidate.venue_a_id)
        venue_b = await session.get(Venue, candidate.venue_b_id)
        if venue_a is None or venue_b is None:
            raise HTTPException(status_code=404, detail="One or both venues not found")

        # venue_b の tournament を venue_a に移管
        t_result = await session.execute(
            select(Tournament).where(Tournament.venue_id == venue_b.id)
        )
        for t in t_result.scalars():
            t.venue_id = venue_a.id

        # sources をマージ（重複排除）
        merged_sources = list(dict.fromkeys(
            (venue_a.sources or []) + (venue_b.sources or [])
        ))
        venue_a.sources = merged_sources

        # venue_a に venue_b の欠落フィールドを補完
        if not venue_a.hours_today and venue_b.hours_today:
            venue_a.hours_today = venue_b.hours_today
        if venue_a.price_entry_min is None and venue_b.price_entry_min is not None:
            venue_a.price_entry_min = venue_b.price_entry_min
            venue_a.price_note = venue_b.price_note
        if venue_a.drink_required is None and venue_b.drink_required is not None:
            venue_a.drink_required = venue_b.drink_required
        if not venue_a.food_level and venue_b.food_level:
            venue_a.food_level = venue_b.food_level
        if not venue_a.table_count and venue_b.table_count:
            venue_a.table_count = venue_b.table_count
        if not venue_a.peak_time and venue_b.peak_time:
            venue_a.peak_time = venue_b.peak_time
        if venue_a.sns_links is None and venue_b.sns_links:
            venue_a.sns_links = venue_b.sns_links
        elif venue_b.sns_links:
            venue_a.sns_links = {**venue_b.sns_links, **(venue_a.sns_links or {})}

        venue_a.last_updated_at = now

        # venue_b を非表示にする
        venue_b.visibility_status = "hidden"

    candidate.status = body.action
    candidate.resolved_at = now
    candidate.resolved_by = body.resolved_by
    candidate.resolution_note = body.note

    await session.flush()
    await session.refresh(candidate)
    return MergeCandidateItem.model_validate(candidate)


@router.patch("/reports/{report_id}", response_model=ReportResponse, status_code=200)
@limiter.limit(_ADMIN_RATE_LIMIT)
async def resolve_report(
    request: Request,
    report_id: uuid.UUID,
    body: ReportResolve,
    session: AsyncSession = Depends(get_session),
) -> ReportResponse:
    """レポートを処理する"""
    result = await session.execute(select(Report).where(Report.id == str(report_id)))
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    before = {"status": report.status}
    now = datetime.now(timezone.utc)

    report.status = body.status
    report.resolved_at = now
    report.resolved_by = body.resolved_by

    # remove申請が承認された場合、対象エンティティを非表示にする
    if body.status == "resolved" and report.report_type == "remove":
        if report.entity_type == "venue":
            entity = await session.get(Venue, report.entity_id)
            if entity:
                entity.visibility_status = "hidden"

    history = ReportHistory(
        report_id=report.id,
        changed_by=body.resolved_by,
        changed_at=now,
        action=body.status,
        before_value=before,
        after_value={"status": body.status, "note": body.note},
    )
    session.add(history)
    await session.flush()
    await session.refresh(report)
    return ReportResponse.model_validate(report)


@router.post("/crawl/trigger", response_model=CrawlTriggerResponse)
@limiter.limit(_ADMIN_RATE_LIMIT)
async def trigger_crawl(
    request: Request,
    limit: int = Query(20, ge=1, le=200),
    source_id: uuid.UUID | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> CrawlTriggerResponse:
    """手動でクロールを即時実行する"""
    from tas.crawler.engine import CrawlEngine

    crawler = CrawlEngine(session)
    count = await crawler.run(limit=limit, source_id=str(source_id) if source_id else None)
    await session.commit()
    return CrawlTriggerResponse(
        processed=count,
        message=f"{count}件のソースをクロールしました",
    )


@router.post("/crawl/reset-stale", response_model=CrawlResetStaleResponse)
@limiter.limit(_ADMIN_RATE_LIMIT)
async def reset_stale_sources(
    request: Request,
    stale_days: int = Query(30, ge=1, le=365),
    session: AsyncSession = Depends(get_session),
) -> CrawlResetStaleResponse:
    """古いデータのソースをpendingにリセットし、次のスケジューラサイクルで再クロールされるようにする"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=stale_days)

    # done状態でlast_run_atが古い、またはNULLのソースをpendingにリセット
    result = await session.execute(
        select(Source).where(
            Source.status == "done",
            (Source.last_run_at.is_(None)) | (Source.last_run_at <= cutoff),
        )
    )
    sources = result.scalars().all()
    for s in sources:
        s.status = "pending"
        s.fail_count = 0
        s.error_reason = None

    await session.flush()
    return CrawlResetStaleResponse(
        reset_count=len(sources),
        message=f"{len(sources)}件のソースをリセットしました（{stale_days}日以上未更新）",
    )


@router.get("/crawl/scheduler-status", response_model=SchedulerStatus)
async def get_scheduler_status() -> SchedulerStatus:
    """スケジューラの設定状態を返す"""
    return SchedulerStatus(
        enabled=settings.scheduler_enabled,
        interval_minutes=settings.scheduler_interval_minutes,
        batch_size=settings.scheduler_batch_size,
        discovery_enabled=settings.discovery_enabled,
        discovery_interval_hours=settings.discovery_interval_hours,
    )


@router.post("/discovery/trigger", response_model=DiscoveryTriggerResponse)
@limiter.limit(_ADMIN_RATE_LIMIT)
async def trigger_discovery(
    request: Request,
    mode: str = Query("all", pattern="^(directories|search|all)$"),
    session: AsyncSession = Depends(get_session),
) -> DiscoveryTriggerResponse:
    """新店舗の自動発見を実行する。

    - directories: まとめサイト登録のみ（数秒で完了 → 同期実行）
    - search: Web検索のみ（数分かかる → バックグラウンド実行）
    - all: 両方（ディレクトリは同期、検索はバックグラウンド）
    """
    import asyncio

    from tas.crawler.web_search import discover_new_directories, search_discover, seed_directory_sources
    from tas.db.session import AsyncSessionLocal

    directories_added = 0

    # ディレクトリ登録は軽いので同期で実行（既知 + 新規まとめサイト発見）
    if mode in ("directories", "all"):
        directories_added = await seed_directory_sources(session)
        new_dirs = await discover_new_directories(session)
        directories_added += new_dirs

    # Web検索は時間がかかるのでバックグラウンドで実行
    if mode in ("search", "all"):
        async def _run_search() -> None:
            async with AsyncSessionLocal() as bg_session:
                try:
                    count = await search_discover(bg_session)
                    logger.info("[DISCOVERY BG] search completed: %d added", count)
                except Exception as e:
                    logger.error("[DISCOVERY BG] search failed: %s", e)

        asyncio.create_task(_run_search())

    if mode == "directories":
        message = f"ディレクトリ {directories_added} 件登録（新規まとめサイト探索含む）"
    elif mode == "search":
        message = "Web検索をバックグラウンドで開始しました"
    else:
        message = f"ディレクトリ {directories_added} 件登録、Web検索をバックグラウンドで開始"

    return DiscoveryTriggerResponse(
        directories_added=directories_added,
        search_added=0,
        message=message,
    )


@router.get("/discovery/pending", response_model=list[DiscoveryVenueItem])
async def get_discovery_pending(
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[DiscoveryVenueItem]:
    """レビュー待ちの発見店舗一覧"""
    result = await session.execute(
        select(Venue)
        .where(Venue.visibility_status == "pending_review")
        .order_by(Venue.created_at.desc())
        .limit(limit).offset(offset)
    )
    return [DiscoveryVenueItem.model_validate(v) for v in result.scalars()]


@router.patch("/discovery/venues/{venue_id}", response_model=DiscoveryVenueItem)
@limiter.limit(_ADMIN_RATE_LIMIT)
async def review_discovery_venue(
    request: Request,
    venue_id: uuid.UUID,
    body: DiscoveryReviewRequest,
    session: AsyncSession = Depends(get_session),
) -> DiscoveryVenueItem:
    """発見店舗を承認（visible）または却下（hidden）する"""
    venue = await session.get(Venue, str(venue_id))
    if venue is None:
        raise HTTPException(status_code=404, detail="Venue not found")
    if venue.visibility_status != "pending_review":
        raise HTTPException(
            status_code=409,
            detail=f"Venue is already {venue.visibility_status}",
        )

    if body.action == "approve":
        venue.visibility_status = "visible"
    else:
        venue.visibility_status = "hidden"

    await session.flush()
    await session.refresh(venue)
    return DiscoveryVenueItem.model_validate(venue)


@router.post("/discovery/bulk-review")
@limiter.limit(_ADMIN_RATE_LIMIT)
async def bulk_review_discovery_venues(
    request: Request,
    body: DiscoveryBulkReviewRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """発見店舗を一括承認/却下する"""
    new_status = "visible" if body.action == "approve" else "hidden"
    updated = 0
    for vid in body.venue_ids:
        venue = await session.get(Venue, vid)
        if venue and venue.visibility_status == "pending_review":
            venue.visibility_status = new_status
            updated += 1
    await session.flush()
    return {"updated": updated, "action": body.action}


@router.get("/venues/stale", response_model=list[VenueCard])
async def get_stale_venues(
    days: int = Query(None, ge=1, le=3650, description="最終更新からの日数（省略時はsettings.stale_daysを使用）"),
    session: AsyncSession = Depends(get_session),
) -> list[VenueCard]:
    """データ鮮度が低い店舗一覧（last_updated_at が古い、または未設定）"""
    threshold_days = days if days is not None else settings.stale_days
    cutoff = datetime.now(timezone.utc) - timedelta(days=threshold_days)

    result = await session.execute(
        select(Venue)
        .where(
            Venue.visibility_status == "visible",
            (Venue.last_updated_at.is_(None)) | (Venue.last_updated_at <= cutoff),
        )
        .order_by(Venue.last_updated_at.asc().nulls_first())
        .limit(_STALE_VENUES_LIMIT)
    )
    return [VenueCard.model_validate(v) for v in result.scalars()]
