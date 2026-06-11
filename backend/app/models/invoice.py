"""ORM models for ServiceChannel invoice webhook sync.

Invoice state arrives via SC webhooks (push), because the
`GET /v3/odata/invoices` read is permission-blocked. Full design +
rationale: docs/architecture/sc-invoice-webhook-sync.md.

Five tables:
  - webhook_events       raw, append-only event log (the source of truth)
  - invoices             materialized invoice state
  - invoice_labors       itemized labor lines (delete-replace per event)
  - invoice_materials    itemized material lines (delete-replace per event)
  - invoice_status_history  audit trail of every status transition

`sc_env` tags every row ('sandbox' | 'production'). Dev and prod are
separate databases, but keeping the column is cheap provenance and lets
the same code run in both.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class WebhookEvent(Base):
    """Raw, verbatim SC webhook deliveries. Append-only.

    The HTTP receiver stores the exact request bytes here and returns 200
    fast; the worker processes rows later. Because we cannot re-fetch
    invoices from the API, this raw log is the only copy we will ever
    have, so a processing bug must never lose data.
    """

    __tablename__ = "webhook_events"
    __table_args__ = (
        # Worker scans only pending rows; partial index keeps it cheap.
        Index(
            "ix_webhook_events_pending",
            "status",
            postgresql_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    sc_env: Mapped[str] = mapped_column(String(20), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    raw_body: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sign_data: Mapped[str | None] = mapped_column(Text)
    signature_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    event_type: Mapped[str | None] = mapped_column(String(80))
    object_id: Mapped[int | None] = mapped_column(BigInteger)
    # sha256(raw_body) hex; ON CONFLICT DO NOTHING makes redelivery a no-op.
    dedupe_key: Mapped[str | None] = mapped_column(String(64), unique=True)
    # pending | processed | skipped_duplicate | dead_letter | invalid_signature
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="pending"
    )
    error: Mapped[str | None] = mapped_column(Text)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Invoice(Base, TimestampMixin):
    """Materialized invoice state, upserted from webhook events.

    Surrogate `id` PK plus two unique indexes carry the real identity:
    `(sc_env, sc_invoice_id)` once known, and
    `(sc_env, invoice_number, coalesce(wo_tracking_number, -1))` which is
    how backfill rows (no sc_invoice_id yet) get adopted by their later
    webhook event.
    """

    __tablename__ = "invoices"
    __table_args__ = (
        Index(
            "uq_invoices_sc_invoice_id",
            "sc_env",
            "sc_invoice_id",
            unique=True,
            postgresql_where=text("sc_invoice_id IS NOT NULL"),
        ),
        Index(
            "uq_invoices_number_wo",
            "sc_env",
            "invoice_number",
            text("coalesce(wo_tracking_number, -1)"),
            unique=True,
        ),
        Index("ix_invoices_wo_tracking_number", "wo_tracking_number"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    sc_invoice_id: Mapped[int | None] = mapped_column(BigInteger)
    sc_env: Mapped[str] = mapped_column(String(20), nullable=False)
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False)
    wo_tracking_number: Mapped[int | None] = mapped_column(BigInteger)
    subscriber_id: Mapped[int | None] = mapped_column(BigInteger)
    provider_id: Mapped[int | None] = mapped_column(BigInteger)
    location_id: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str | None] = mapped_column(String(40))
    trade: Mapped[str | None] = mapped_column(String(100))
    category: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[str | None] = mapped_column(String(10))
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    invoice_tax: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    invoice_total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    approval_code: Mapped[str | None] = mapped_column(String(80))
    batch_number: Mapped[str | None] = mapped_column(String(80))
    comments: Mapped[str | None] = mapped_column(Text)
    invoice_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    posted_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_action_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # UpdatedDateDTO from the latest applied event; gates out-of-order updates.
    sc_updated_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # webhook | backfill


class InvoiceLabor(Base):
    """Itemized labor line. Replaced wholesale on each event carrying a
    non-empty Labors array (empty arrays must not wipe existing lines)."""

    __tablename__ = "invoice_labors"
    __table_args__ = (
        Index("ix_invoice_labors_invoice", "sc_env", "sc_invoice_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    sc_env: Mapped[str] = mapped_column(String(20), nullable=False)
    sc_invoice_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    skill_level: Mapped[int | None] = mapped_column(Integer)
    labor_type: Mapped[int | None] = mapped_column(Integer)
    num_of_tech: Mapped[int | None] = mapped_column(Integer)
    hourly_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    hours: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))


class InvoiceMaterial(Base):
    """Itemized material line. Same delete-and-replace rule as labors."""

    __tablename__ = "invoice_materials"
    __table_args__ = (
        Index("ix_invoice_materials_invoice", "sc_env", "sc_invoice_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    sc_env: Mapped[str] = mapped_column(String(20), nullable=False)
    sc_invoice_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    part_num: Mapped[str | None] = mapped_column(String(100))
    unit_type: Mapped[int | None] = mapped_column(Integer)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))


class InvoiceStatusHistory(Base):
    """Append-only audit trail of every invoice status transition."""

    __tablename__ = "invoice_status_history"
    __table_args__ = (
        Index("ix_invoice_status_history_invoice", "sc_env", "sc_invoice_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    sc_env: Mapped[str] = mapped_column(String(20), nullable=False)
    sc_invoice_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str | None] = mapped_column(String(40))
    changed_by: Mapped[str | None] = mapped_column(String(200))
    event_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    webhook_event_id: Mapped[int | None] = mapped_column(
        ForeignKey("webhook_events.id")
    )
