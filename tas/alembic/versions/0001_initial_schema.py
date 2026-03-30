"""initial schema (POCUS)

Revision ID: 0001
Revises:
Create Date: 2026-03-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # venues
    op.create_table(
        "venues",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("address", sa.Text(), nullable=False, server_default=""),
        sa.Column("area_prefecture", sa.Text(), nullable=True),
        sa.Column("area_city", sa.Text(), nullable=True),
        sa.Column("lat", sa.Numeric(9, 6), nullable=True),
        sa.Column("lng", sa.Numeric(9, 6), nullable=True),
        sa.Column("open_status", sa.Text(), nullable=False, server_default="unknown"),
        sa.Column("hours_today", sa.Text(), nullable=True),
        sa.Column("price_entry_min", sa.Integer(), nullable=True),
        sa.Column("price_note", sa.Text(), nullable=True),
        sa.Column("drink_required", sa.Boolean(), nullable=True),
        sa.Column("food_level", sa.Text(), nullable=True),
        sa.Column("table_count", sa.Integer(), nullable=True),
        sa.Column("peak_time", sa.Text(), nullable=True),
        sa.Column("website_url", sa.Text(), nullable=True),
        sa.Column("sns_links", postgresql.JSONB(), nullable=True),
        sa.Column("sources", postgresql.JSONB(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("verification_status", sa.Text(), nullable=False, server_default="unverified"),
        sa.Column("visibility_status", sa.Text(), nullable=False, server_default="visible"),
        sa.Column("match_confidence", sa.Numeric(3, 2), nullable=True),
        sa.Column("country_code", sa.Text(), nullable=False, server_default="JP"),
        sa.Column("locale", sa.Text(), nullable=False, server_default="ja"),
        sa.Column("time_zone", sa.Text(), nullable=False, server_default="Asia/Tokyo"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # tournaments
    op.create_table(
        "tournaments",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("venue_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("buy_in", sa.Integer(), nullable=True),
        sa.Column("guarantee", sa.Integer(), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("url", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.Text(), nullable=False, server_default="scheduled"),
        sa.Column(
            "last_updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["venue_id"], ["venues.id"], ondelete="CASCADE"),
    )

    # venue_merge_candidates
    op.create_table(
        "venue_merge_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("venue_a_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("venue_b_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("similarity_score", sa.Numeric(3, 2), nullable=True),
        sa.Column("evidence", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["venue_a_id"], ["venues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["venue_b_id"], ["venues.id"], ondelete="CASCADE"),
    )

    # sources
    op.create_table(
        "sources",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("seed_url", sa.Text(), nullable=False, unique=True),
        sa.Column("canonical_url", sa.Text(), nullable=True),
        sa.Column("seed_type", sa.Text(), nullable=True),
        sa.Column("region_hint", sa.Text(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("page_kind", sa.Text(), nullable=True),
        sa.Column("owner", sa.Text(), nullable=True),
        sa.Column("source_name", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fail_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_reason", sa.Text(), nullable=True),
        sa.Column("cooldown_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("update_interval_hours", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # crawl_logs
    op.create_table(
        "crawl_logs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("fetched_title", sa.Text(), nullable=True),
        sa.Column("meta_description", sa.Text(), nullable=True),
        sa.Column("h1", sa.Text(), nullable=True),
        sa.Column("links_count", sa.Integer(), nullable=True),
        sa.Column("checksum", sa.Text(), nullable=True),
        sa.Column("parse_method", sa.Text(), nullable=True),
        sa.Column("field_confidence", postgresql.JSONB(), nullable=True),
        sa.Column("robots_blocked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "crawled_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
    )

    # reports
    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("report_type", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("reporter_name", sa.Text(), nullable=True),
        sa.Column("reporter_contact", sa.Text(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # report_history
    op.create_table(
        "report_history",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("report_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("changed_by", sa.Text(), nullable=True),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("action", sa.Text(), nullable=True),
        sa.Column("before_value", postgresql.JSONB(), nullable=True),
        sa.Column("after_value", postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
    )

    # インデックス
    op.create_index("ix_venues_area_prefecture", "venues", ["area_prefecture"])
    op.create_index("ix_venues_open_status", "venues", ["open_status"])
    op.create_index("ix_venues_visibility_status", "venues", ["visibility_status"])
    op.create_index("ix_venues_lat_lng", "venues", ["lat", "lng"])
    op.create_index("ix_tournaments_venue_id", "tournaments", ["venue_id"])
    op.create_index("ix_tournaments_start_at", "tournaments", ["start_at"])
    op.create_index("ix_tournaments_status", "tournaments", ["status"])
    op.create_index("ix_venue_merge_candidates_status", "venue_merge_candidates", ["status"])
    op.create_index("ix_sources_status", "sources", ["status"])
    op.create_index("ix_sources_priority", "sources", ["priority"])
    op.create_index("ix_crawl_logs_source_id", "crawl_logs", ["source_id"])
    op.create_index("ix_reports_entity_type_entity_id", "reports", ["entity_type", "entity_id"])
    op.create_index("ix_reports_status", "reports", ["status"])


def downgrade() -> None:
    op.drop_table("report_history")
    op.drop_table("reports")
    op.drop_table("crawl_logs")
    op.drop_table("sources")
    op.drop_table("venue_merge_candidates")
    op.drop_table("tournaments")
    op.drop_table("venues")
