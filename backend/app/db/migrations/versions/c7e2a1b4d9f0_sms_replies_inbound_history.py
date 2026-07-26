"""sms_replies inbound history table

Revision ID: c7e2a1b4d9f0
Revises: 3f1cd1fcda86
Create Date: 2026-07-20 22:40:00.000000

Hand-authored (dev Supabase was paused at write time, so autogenerate
couldn't diff). Mirrors the SmsReply model in app/models/work_order.py.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7e2a1b4d9f0"
down_revision: str | Sequence[str] | None = "3f1cd1fcda86"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sms_replies",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("twilio_message_sid", sa.String(length=64), nullable=True),
        sa.Column("from_number", sa.String(length=32), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("num_media", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("vendor_id", sa.Integer(), nullable=True),
        sa.Column("work_order_id", sa.Integer(), nullable=True),
        sa.Column("is_opt_out", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("forwarded", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["vendor_id"], ["vendors.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("twilio_message_sid", name="uq_sms_replies_twilio_message_sid"),
    )
    op.create_index("ix_sms_replies_vendor_id", "sms_replies", ["vendor_id"], unique=False)

    # New public tables must have RLS enabled (Supabase advisor); the backend
    # connects as postgres/bypassrls so this is a no-op for us. RLS on the
    # table disappears automatically when it is dropped in downgrade().
    op.execute("ALTER TABLE public.sms_replies ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index("ix_sms_replies_vendor_id", table_name="sms_replies")
    op.drop_table("sms_replies")
