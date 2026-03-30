"""Pydanticスキーマ定義（POCUS）"""

import re
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

_JST = timezone(timedelta(hours=9))
# スペース有りセパレーター・25:00形式に対応
_RANGE_RE = re.compile(r"(\d{1,2}):(\d{2})\s*[〜～~\-]\s*(翌)?(\d{1,2}):(\d{2})")
# 定休日：日曜日 / 定休日：月・水 などを解析
_KYUJITSU_RE = re.compile(r"定休日[：:\s]*([月火水木金土日](?:[・、,/][月火水木金土日])*)")
_DAY_MAP = {"月": 0, "火": 1, "水": 2, "木": 3, "金": 4, "土": 5, "日": 6}


def _is_kyujitsu_today(hours: str, weekday: int) -> bool:
    """定休日パターンを解析して今日が定休日かどうか返す。"""
    for m in _KYUJITSU_RE.finditer(hours):
        for ch, wd in _DAY_MAP.items():
            if ch in m.group(1) and wd == weekday:
                return True
    return False


def _infer_open_status(hours_today: str | None) -> str:
    """hours_todayテキストと現在JST時刻からopen/closed/unknownを返す。"""
    if not hours_today:
        return "unknown"

    now_jst = datetime.now(_JST)
    now_min = now_jst.hour * 60 + now_jst.minute
    weekday = now_jst.weekday()  # 0=月 … 6=日
    is_weekend = weekday >= 5

    # 「本日休業」は即確定
    if "本日休業" in hours_today:
        return "closed"

    # 「定休日：〇曜日」が今日に該当するか確認
    if "定休日" in hours_today and _is_kyujitsu_today(hours_today, weekday):
        return "closed"

    ranges: list[tuple[int, int]] = []

    # "/" "／" 改行でセグメント分割
    for seg in re.split(r"[/／\n]", hours_today):
        seg = seg.strip()
        if not seg:
            continue

        # 曜日ルール判定（セグメントが特定曜日向けか）
        has_weekday = bool(re.search(r"[月火水木金]|平日", seg))
        has_weekend = bool(re.search(r"[土日]|祝", seg))
        if has_weekday and not has_weekend and is_weekend:
            continue  # 平日ルールだが今日は土日祝
        if has_weekend and not has_weekday and not is_weekend:
            continue  # 土日祝ルールだが今日は平日

        for m in _RANGE_RE.finditer(seg):
            open_h, open_m = int(m.group(1)), int(m.group(2))
            next_day_flag = m.group(3) == "翌"
            close_h, close_m = int(m.group(4)), int(m.group(5))

            open_min = open_h * 60 + open_m
            # 25:00 形式（close_h >= 24）も翌日扱い
            close_min = (close_h % 24) * 60 + close_m
            if next_day_flag or close_h >= 24:
                close_min += 1440
            # 「翌」なしでも close <= open なら翌日扱い（例: 22:00〜5:00）
            elif close_min <= open_min:
                close_min += 1440

            ranges.append((open_min, close_min))

    if not ranges:
        return "unknown"

    for open_min, close_min in ranges:
        if close_min > 1440:
            # 深夜をまたぐ: 開店時刻以降 OR 翌日の閉店時刻前
            if now_min >= open_min or now_min < close_min - 1440:
                return "open"
        else:
            if open_min <= now_min < close_min:
                return "open"

    return "closed"


# ── 地図ピン ──
class VenuePin(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type: str = "venue"
    lat: float
    lng: float
    display_name: str
    open_status: str  # open / closed / unknown
    hours_today: Optional[str] = None
    price_entry_min: Optional[int] = None
    next_tournament_title: Optional[str] = None
    next_tournament_start: Optional[datetime] = None
    area_prefecture: Optional[str] = None
    area_city: Optional[str] = None
    verification_status: str
    detail_url: str
    booking_url: Optional[str] = None
    # スコア算出用
    food_level: Optional[str] = None
    table_count: Optional[int] = None
    drink_required: Optional[bool] = None

    @model_validator(mode="after")
    def _compute_open_status(self) -> "VenuePin":
        if self.open_status == "unknown":
            self.open_status = _infer_open_status(self.hours_today)
        return self


class VenuePinsResponse(BaseModel):
    pins: list[VenuePin]
    total: int


# ── 店舗カード（一覧用） ──
class VenueCard(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    # P0
    open_status: str
    hours_today: Optional[str] = None
    price_entry_min: Optional[int] = None
    price_note: Optional[str] = None
    next_tournament_title: Optional[str] = None
    next_tournament_start: Optional[datetime] = None
    next_tournament_url: Optional[str] = None
    # P1 アイコン
    drink_required: Optional[bool] = None
    food_level: Optional[str] = None
    table_count: Optional[int] = None
    peak_time: Optional[str] = None
    # 位置
    address: Optional[str] = None
    area_prefecture: Optional[str] = None
    area_city: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    # メタ
    last_updated_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    data_age_days: Optional[int] = None
    sources: Optional[list[str]] = None

    @model_validator(mode="after")
    def _compute_open_status(self) -> "VenueCard":
        if self.open_status == "unknown":
            self.open_status = _infer_open_status(self.hours_today)
        return self

    @model_validator(mode="after")
    def _compute_data_age(self) -> "VenueCard":
        base = self.last_updated_at or self.updated_at
        if base is not None:
            ref = base if base.tzinfo else base.replace(tzinfo=timezone.utc)
            self.data_age_days = (datetime.now(timezone.utc) - ref).days
        return self


# ── 大会 ──
class TournamentBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    start_at: Optional[datetime] = None
    buy_in: Optional[int] = None
    guarantee: Optional[int] = None
    capacity: Optional[int] = None
    url: str
    status: str


# ── 店舗詳細 ──
class VenueDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    address: str
    area_prefecture: Optional[str] = None
    area_city: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    # P0
    open_status: str
    hours_today: Optional[str] = None
    price_entry_min: Optional[int] = None
    price_note: Optional[str] = None
    # P1
    drink_required: Optional[bool] = None
    food_level: Optional[str] = None
    table_count: Optional[int] = None
    peak_time: Optional[str] = None
    # メタ
    website_url: Optional[str] = None
    sns_links: Optional[dict[str, str]] = None
    sources: Optional[list[str]] = None
    summary: Optional[str] = None
    verification_status: str
    visibility_status: str
    match_confidence: Optional[float] = None
    field_confidence: Optional[dict] = None
    country_code: str
    locale: str
    time_zone: str
    last_updated_at: Optional[datetime] = None
    data_age_days: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    # リレーション
    tournaments: list[TournamentBrief] = []

    @model_validator(mode="after")
    def _compute_open_status(self) -> "VenueDetail":
        if self.open_status == "unknown":
            self.open_status = _infer_open_status(self.hours_today)
        return self

    @model_validator(mode="after")
    def _compute_data_age(self) -> "VenueDetail":
        base = self.last_updated_at or self.updated_at
        if base is not None:
            ref = base if base.tzinfo else base.replace(tzinfo=timezone.utc)
            self.data_age_days = (datetime.now(timezone.utc) - ref).days
        return self


# ── 店舗一覧レスポンス ──
class VenueListResponse(BaseModel):
    items: list[VenueCard]
    total: int
    offset: int
    limit: int


# ── マージ候補 ──
class MergeCandidateItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    venue_a_id: str
    venue_b_id: str
    similarity_score: Optional[float] = None
    evidence: Optional[dict] = None
    status: str
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_note: Optional[str] = None
    created_at: datetime


# ── マージ候補解決 ──
class MergeCandidateResolve(BaseModel):
    """merged: venue_b を venue_a に統合 / rejected: 候補を却下"""
    action: Literal["merged", "rejected"]
    resolved_by: Optional[str] = Field(None, max_length=200)
    note: Optional[str] = Field(None, max_length=5000)


# ── 管理ダッシュボード ──
class AdminStats(BaseModel):
    total_venues: int
    total_tournaments: int
    total_sources: int
    pending_sources: int
    running_sources: int
    error_sources: int
    done_sources: int
    disabled_sources: int
    blocked_suspected_sources: int
    total_crawl_logs: int
    low_confidence_venues: int
    pending_reports: int
    pending_merge_candidates: int


class RecentEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    type: str  # "venue" | "tournament"
    area_prefecture: Optional[str] = None
    area_city: Optional[str] = None
    match_confidence: Optional[float] = None
    created_at: datetime


class SourceItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    seed_url: str
    seed_type: Optional[str] = None
    status: str
    fail_count: int
    last_run_at: Optional[datetime] = None
    error_reason: Optional[str] = None


# ── レポート ──
class CrawlTriggerResponse(BaseModel):
    processed: int
    message: str


class CrawlResetStaleResponse(BaseModel):
    reset_count: int
    message: str


class SchedulerStatus(BaseModel):
    enabled: bool
    interval_minutes: int
    batch_size: int
    discovery_enabled: bool = False
    discovery_interval_hours: int = 24


class DiscoveryTriggerResponse(BaseModel):
    directories_added: int
    search_added: int
    message: str


class ReportCreate(BaseModel):
    report_type: Literal["remove", "correct", "claim_owner"]
    entity_type: Literal["venue"] = "venue"
    entity_id: str = Field(max_length=36)
    reporter_name: Optional[str] = Field(None, max_length=200)
    reporter_contact: Optional[str] = Field(None, max_length=200)
    details: Optional[str] = Field(None, max_length=5000)


class ReportResolve(BaseModel):
    status: Literal["resolved", "rejected"]
    resolved_by: Optional[str] = Field(None, max_length=200)
    note: Optional[str] = Field(None, max_length=5000)


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    report_type: str
    entity_type: str
    entity_id: str
    status: str
    reporter_name: Optional[str] = None
    details: Optional[str] = None
    resolved_by: Optional[str] = None
    created_at: datetime


# ── 発見レビュー ──
class DiscoveryVenueItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    address: Optional[str] = None
    area_prefecture: Optional[str] = None
    area_city: Optional[str] = None
    website_url: Optional[str] = None
    sources: Optional[list] = None
    match_confidence: Optional[float] = None
    # 精査用の追加情報
    hours_today: Optional[str] = None
    price_entry_min: Optional[int] = None
    price_note: Optional[str] = None
    table_count: Optional[int] = None
    food_level: Optional[str] = None
    summary: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    created_at: datetime


class DiscoveryReviewRequest(BaseModel):
    action: Literal["approve", "reject"]


class DiscoveryBulkReviewRequest(BaseModel):
    venue_ids: list[str] = Field(max_length=500)  # UUIDはDB内でstr保存
    action: Literal["approve", "reject"]

    @model_validator(mode="after")
    def _validate_venue_ids(self) -> "DiscoveryBulkReviewRequest":
        import re
        _uuid_re = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
        for vid in self.venue_ids:
            if not _uuid_re.match(vid):
                raise ValueError(f"Invalid UUID format: {vid}")
        return self
