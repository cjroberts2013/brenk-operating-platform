"""work_orders brenk_total_override

Directly-entered pre-tax total bill, for when Daryl prices a WO by the
total instead of breaking out vendor labor/material + markup.

Revision ID: a1b2c3d4e5f6
Revises: 93c84ffb76c3
Create Date: 2026-06-14 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "93c84ffb76c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "work_orders",
        sa.Column("brenk_total_override", sa.Numeric(precision=12, scale=2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("work_orders", "brenk_total_override")
