"""work_orders.brenk_sc_deleted_at (SC-deleted marker)

Revision ID: d4a9f1c2b8e3
Revises: c7e2a1b4d9f0
Create Date: 2026-09-06 15:05:00.000000

Hand-authored (dev Supabase pooler was flapping at write time).
Additive nullable column — see the SmsReply/access-flag migrations for the
same pattern.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4a9f1c2b8e3"
down_revision: str | Sequence[str] | None = "c7e2a1b4d9f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "work_orders",
        sa.Column("brenk_sc_deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("work_orders", "brenk_sc_deleted_at")
