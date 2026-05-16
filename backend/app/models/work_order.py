"""ORM models for work orders and related entities.

Schema designed from real ServiceChannel v3 API responses captured during
Phase 1 exploration. See docs/api-samples/ for source payloads and
docs/architecture/database-schema.md for design rationale.
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
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

# =============================================================================
# Reference / Lookup tables
# =============================================================================


class Trade(Base, TimestampMixin):
    """A type of work (Roofing, Plumbing, Electrical, etc.)."""

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sc_trade_id: Mapped[int | None] = mapped_column(Integer, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    work_orders: Mapped[list["WorkOrder"]] = relationship(back_populates="trade")

    def __repr__(self) -> str:
        return f"<Trade {self.name}>"


# =============================================================================
# Core business entities
# =============================================================================


class Client(Base, TimestampMixin):
    """A client / subscriber that originates work orders (e.g., CubeSmart)."""

    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sc_subscriber_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(255))
    is_outsourced: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    raw_data: Mapped[dict | None] = mapped_column(JSONB)

    locations: Mapped[list["Location"]] = relationship(back_populates="client")
    work_orders: Mapped[list["WorkOrder"]] = relationship(back_populates="client")

    def __repr__(self) -> str:
        return f"<Client {self.name}>"


class Location(Base, TimestampMixin):
    """A physical location belonging to a client (e.g., a specific CubeSmart store)."""

    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sc_location_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False, index=True)
    store_id: Mapped[str | None] = mapped_column(String(50), index=True)
    name: Mapped[str | None] = mapped_column(String(500))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    region: Mapped[str | None] = mapped_column(String(50))
    district: Mapped[str | None] = mapped_column(String(50))
    timezone_offset: Mapped[int | None] = mapped_column(Integer)
    is_international: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    raw_data: Mapped[dict | None] = mapped_column(JSONB)

    client: Mapped["Client"] = relationship(back_populates="locations")
    work_orders: Mapped[list["WorkOrder"]] = relationship(back_populates="location")

    def __repr__(self) -> str:
        return f"<Location {self.store_id} {self.name}>"


class Vendor(Base, TimestampMixin):
    """A sub-vendor that Brenk dispatches work to.

    Note: sc_provider_id is nullable — Brenk may track vendors that are not
    represented as Providers in ServiceChannel.
    """

    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sc_provider_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    raw_data: Mapped[dict | None] = mapped_column(JSONB)

    work_orders: Mapped[list["WorkOrder"]] = relationship(back_populates="assigned_vendor")

    def __repr__(self) -> str:
        return f"<Vendor {self.name}>"


# =============================================================================
# Work Orders
# =============================================================================


class WorkOrder(Base, TimestampMixin):
    """A work order synced from ServiceChannel, with Brenk-specific metadata layered on top."""

    __tablename__ = "work_orders"
    __table_args__ = (
        Index("ix_work_orders_primary_status", "primary_status"),
        Index("ix_work_orders_sc_updated_date", "sc_updated_date"),
        Index("ix_work_orders_scheduled_date", "scheduled_date"),
    )

    # Identity
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sc_work_order_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    sc_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    sc_purchase_number: Mapped[str | None] = mapped_column(String(50))

    # Relationships
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), index=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"), index=True)
    trade_id: Mapped[int | None] = mapped_column(ForeignKey("trades.id"), index=True)
    assigned_vendor_id: Mapped[int | None] = mapped_column(ForeignKey("vendors.id"), index=True)

    # Status (denormalized for query speed; primary+extended together form full state)
    primary_status: Mapped[str] = mapped_column(String(50), nullable=False)
    extended_status: Mapped[str | None] = mapped_column(String(100))
    can_create_invoice: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Categorization
    category: Mapped[str | None] = mapped_column(String(100))
    sc_category_id: Mapped[int | None] = mapped_column(Integer)
    priority: Mapped[str | None] = mapped_column(String(100))
    problem_code: Mapped[str | None] = mapped_column(String(100))

    # Content
    description: Mapped[str | None] = mapped_column(Text)
    resolution: Mapped[str | None] = mapped_column(Text)
    caller: Mapped[str | None] = mapped_column(String(255))
    approval_code: Mapped[str | None] = mapped_column(String(50))

    # Money
    nte: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency_code: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)

    # Dates (stored as UTC)
    call_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scheduled_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expiration_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    original_eta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sc_updated_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Flags
    is_invoiced: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_expired: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_check_in_denied: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_work_activity: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auto_complete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auto_invoice: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Counts (denormalized from SC inline data)
    notes_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attachments_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Sync metadata
    raw_data: Mapped[dict | None] = mapped_column(JSONB)
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    # Relationships
    client: Mapped["Client | None"] = relationship(back_populates="work_orders")
    location: Mapped["Location | None"] = relationship(back_populates="work_orders")
    trade: Mapped["Trade | None"] = relationship(back_populates="work_orders")
    assigned_vendor: Mapped["Vendor | None"] = relationship(back_populates="work_orders")
    notes: Mapped[list["WorkOrderNote"]] = relationship(
        back_populates="work_order", cascade="all, delete-orphan"
    )
    status_history: Mapped[list["WorkOrderStatusHistory"]] = relationship(
        back_populates="work_order", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<WorkOrder #{self.sc_number} status={self.primary_status}>"


class WorkOrderNote(Base, TimestampMixin):
    """A note on a work order — sourced from ServiceChannel or created internally by Brenk."""

    __tablename__ = "wo_notes"
    __table_args__ = (
        UniqueConstraint("sc_note_id", name="uq_wo_notes_sc_note_id"),
        Index("ix_wo_notes_work_order_id", "work_order_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id"), nullable=False)
    sc_note_id: Mapped[int | None] = mapped_column(BigInteger)
    sc_document_id: Mapped[str | None] = mapped_column(String(64))
    note_number: Mapped[int | None] = mapped_column(Integer)
    note_data: Mapped[str] = mapped_column(Text, nullable=False)
    note_type: Mapped[str | None] = mapped_column(String(50))  # "SystemNote", "UserNote", etc.
    visibility: Mapped[int | None] = mapped_column(Integer)
    action_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_attachment_note: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(255))
    company_name: Mapped[str | None] = mapped_column(String(255))
    created_at_sc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(20), default="servicechannel", nullable=False)
    raw_data: Mapped[dict | None] = mapped_column(JSONB)

    work_order: Mapped["WorkOrder"] = relationship(back_populates="notes")

    def __repr__(self) -> str:
        return f"<WorkOrderNote #{self.note_number} wo={self.work_order_id}>"


class WorkOrderStatusHistory(Base):
    """Historical record of status changes for a work order."""

    __tablename__ = "wo_status_history"
    __table_args__ = (Index("ix_wo_status_history_work_order_id", "work_order_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id"), nullable=False)
    primary_status: Mapped[str] = mapped_column(String(50), nullable=False)
    extended_status: Mapped[str | None] = mapped_column(String(100))
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
    changed_by: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(20), default="servicechannel", nullable=False)

    work_order: Mapped["WorkOrder"] = relationship(back_populates="status_history")

    def __repr__(self) -> str:
        return f"<StatusHistory wo={self.work_order_id} {self.primary_status}/{self.extended_status}>"
