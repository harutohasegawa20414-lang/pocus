"""add resolved_by and resolution_note to venue_merge_candidates

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-05 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "venue_merge_candidates",
        sa.Column("resolved_by", sa.Text(), nullable=True),
    )
    op.add_column(
        "venue_merge_candidates",
        sa.Column("resolution_note", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("venue_merge_candidates", "resolution_note")
    op.drop_column("venue_merge_candidates", "resolved_by")
