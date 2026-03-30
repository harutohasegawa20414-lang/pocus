"""add field_confidence to venues

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-05 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "venues",
        sa.Column("field_confidence", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("venues", "field_confidence")
