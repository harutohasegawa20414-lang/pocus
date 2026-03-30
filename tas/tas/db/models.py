"""SQLAlchemy ORM モデル（POCUS 全エンティティ）"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# TIMESTAMPTZ = timezone-aware TIMESTAMP
TIMESTAMPTZ = DateTime(timezone=True)


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Venue(Base):
    """ポーカー店舗"""
    __tablename__ = "venues"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False, default="")
    area_prefecture: Mapped[str | None] = mapped_column(Text, nullable=True)
    area_city: Mapped[str | None] = mapped_column(Text, nullable=True)
    lat: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    lng: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)

    # P0: 営業情報
    open_status: Mapped[str] = mapped_column(
        Text, nullable=False, default="unknown"
    )  # open / preparing / closed / unknown
    hours_today: Mapped[str | None] = mapped_column(Text, nullable=True)

    # P0: 金額
    price_entry_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # P1: 施設情報
    drink_required: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    food_level: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # none / basic / rich
    table_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    peak_time: Mapped[str | None] = mapped_column(Text, nullable=True)

    # メタ
    website_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    sns_links: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    sources: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # 根拠URL配列
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # フィールドごとの信頼度（H/M/L）: クロール時に更新
    field_confidence: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    verification_status: Mapped[str] = mapped_column(
        Text, nullable=False, default="unverified"
    )
    visibility_status: Mapped[str] = mapped_column(
        Text, nullable=False, default="pending_review"
    )
    match_confidence: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    country_code: Mapped[str] = mapped_column(Text, nullable=False, default="JP")
    locale: Mapped[str] = mapped_column(Text, nullable=False, default="ja")
    time_zone: Mapped[str] = mapped_column(Text, nullable=False, default="Asia/Tokyo")
    # ソースから最後にデータを取得・更新した日時（クロール時に明示的にセット）
    last_updated_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMPTZ, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, default=_now, onupdate=_now
    )

    tournaments: Mapped[list["Tournament"]] = relationship(
        "Tournament", back_populates="venue"
    )


class Tournament(Base):
    """ポーカー大会"""
    __tablename__ = "tournaments"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    venue_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("venues.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    start_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)
    buy_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    guarantee: Mapped[int | None] = mapped_column(Integer, nullable=True)
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="scheduled"
    )  # scheduled / canceled / unknown
    last_updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, default=_now
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, default=_now
    )

    venue: Mapped["Venue"] = relationship("Venue", back_populates="tournaments")


class VenueMergeCandidate(Base):
    """店舗統合候補（重複対策）"""
    __tablename__ = "venue_merge_candidates"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    venue_a_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("venues.id", ondelete="CASCADE"), nullable=False
    )
    venue_b_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("venues.id", ondelete="CASCADE"), nullable=False
    )
    similarity_score: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    evidence: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="pending"
    )  # pending / merged / rejected
    resolved_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, default=_now
    )


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    seed_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    canonical_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # seed_type有効値: "manual" / "directory" / "venue_official" / "sheets"
    seed_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    region_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    page_kind: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    last_run_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)
    fail_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    cooldown_until: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)
    # ソースごとの更新頻度設定（タスク12対応）
    update_interval_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Google Sheetsのシート行番号（書き戻し用）
    sheet_row_num: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, default=_now, onupdate=_now
    )

    crawl_logs: Mapped[list["CrawlLog"]] = relationship(
        "CrawlLog", back_populates="source"
    )


class CrawlLog(Base):
    __tablename__ = "crawl_logs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fetched_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    h1: Mapped[str | None] = mapped_column(Text, nullable=True)
    links_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checksum: Mapped[str | None] = mapped_column(Text, nullable=True)
    parse_method: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_confidence: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    robots_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    crawled_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, default=_now
    )

    source: Mapped["Source"] = relationship("Source", back_populates="crawl_logs")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    report_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)  # venue
    entity_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    reporter_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    reporter_contact: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    resolved_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, default=_now
    )

    history: Mapped[list["ReportHistory"]] = relationship(
        "ReportHistory", back_populates="report"
    )


class ReportHistory(Base):
    __tablename__ = "report_history"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    report_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False
    )
    changed_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, default=_now
    )
    action: Mapped[str | None] = mapped_column(Text, nullable=True)
    before_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    report: Mapped["Report"] = relationship("Report", back_populates="history")
