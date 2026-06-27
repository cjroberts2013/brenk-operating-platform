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
    text,
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

    # Brenk-internal markup default. Null = no default set yet; the
    # invoice helper offers no suggestion and Daryl enters a number
    # manually. See the "Markup Helper Design" section of CLAUDE.md
    # for the full rationale.
    default_markup_percent: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    work_orders: Mapped[list["WorkOrder"]] = relationship(back_populates="trade")

    def __repr__(self) -> str:
        return f"<Trade {self.name}>"


class JobType(Base, TimestampMixin):
    """A Brenk job type — the single shared taxonomy used for BOTH AI
    work-order categorization (`work_orders.brenk_category`) and vendor
    skills (`vendor_job_types`).

    Replaces the old hardcoded `app/services/categories.py` list so Daryl can
    add/rename types from the dashboard as new trades arise. The `description`
    guides the Gemini categorizer. Distinct from SC's `trade` (the often-wrong
    skill SC puts on a WO) — this is Brenk's own clean vocabulary.
    """

    __tablename__ = "job_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    # One-line description guiding the categorizer's classification.
    description: Mapped[str | None] = mapped_column(Text)
    # Display order (lower first); ties broken by name.
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Soft-retire: inactive types stay for history but drop out of pickers
    # and the categorizer's choices.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # The catch-all ("Other") — kept last and never offered as a vendor skill.
    is_catchall: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def __repr__(self) -> str:
        return f"<JobType {self.name}>"


# =============================================================================
# Core business entities
# =============================================================================


class Client(Base, TimestampMixin):
    """A client / subscriber that originates work orders (e.g., CubeSmart)."""

    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sc_subscriber_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
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

    # Brenk-internal enrichment (added 2026-06-20). None of these exist in
    # ServiceChannel — they're operational knowledge Daryl keeps about a
    # site. The work-order sync MUST NOT write these: upsert_location()
    # writes only an explicit SC-field allowlist, mirroring the vendor sync
    # that never clobbers Brenk-internal vendor fields.
    district_manager_name: Mapped[str | None] = mapped_column(String(255))
    district_manager_phone: Mapped[str | None] = mapped_column(String(50))
    district_manager_email: Mapped[str | None] = mapped_column(String(255))
    # 3-tier operational health flag: "good" | "watch" | "problem".
    # Plain String, not a DB enum — matches work_orders.primary_status and
    # vendor.contact_preference; the closed set is enforced in the Pydantic
    # layer (Literal). NULL = unrated (a site Daryl hasn't reviewed yet);
    # deliberately not defaulted to "good" so unreviewed sites don't read
    # as healthy.
    rating: Mapped[str | None] = mapped_column(String(20))
    # Free-text running notes / context Daryl accumulates on the location.
    description: Mapped[str | None] = mapped_column(Text)

    client: Mapped["Client"] = relationship(back_populates="locations")
    work_orders: Mapped[list["WorkOrder"]] = relationship(back_populates="location")
    gate_codes: Mapped[list["GateCode"]] = relationship(
        back_populates="location",
        cascade="all, delete-orphan",
        order_by="GateCode.created_at.desc()",
    )

    def __repr__(self) -> str:
        return f"<Location {self.store_id} {self.name}>"


class GateCode(Base, TimestampMixin):
    """A gate / access code for a location.

    Codes are never edited in place. When a code changes, the old row is
    *invalidated* (is_active=False, invalidated_at set) and a new active row
    is added — so the history of what the code used to be is preserved. A
    location may have several active codes at once (e.g. "front gate" and
    "loading dock"), distinguished by `label`.
    """

    __tablename__ = "gate_codes"
    __table_args__ = (
        Index("ix_gate_codes_location_id", "location_id"),
        # Hot path: the currently-active codes for a location. Partial index
        # keeps it small.
        Index(
            "ix_gate_codes_location_active",
            "location_id",
            postgresql_where=text("is_active"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str | None] = mapped_column(String(100))
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    location: Mapped["Location"] = relationship(back_populates="gate_codes")

    def __repr__(self) -> str:
        state = "active" if self.is_active else "invalidated"
        return f"<GateCode {self.code} ({state}) loc={self.location_id}>"


class VendorTrade(Base):
    """Many-to-many junction between vendors and trades they specialize in.

    Composite primary key — each (vendor, trade) pair appears at most
    once. No surrogate id since rows here are intrinsically identified
    by the pair.
    """

    __tablename__ = "vendor_trades"

    vendor_id: Mapped[int] = mapped_column(
        ForeignKey("vendors.id", ondelete="CASCADE"), primary_key=True
    )
    trade_id: Mapped[int] = mapped_column(
        ForeignKey("trades.id", ondelete="CASCADE"), primary_key=True
    )


class VendorJobType(Base):
    """Many-to-many junction between vendors and the job types (skills) they
    do — the shared taxonomy that also drives AI categorization. Replaces the
    old `vendor_trades` link as the source of vendor skills.
    """

    __tablename__ = "vendor_job_types"

    vendor_id: Mapped[int] = mapped_column(
        ForeignKey("vendors.id", ondelete="CASCADE"), primary_key=True
    )
    job_type_id: Mapped[int] = mapped_column(
        ForeignKey("job_types.id", ondelete="CASCADE"), primary_key=True
    )


class Vendor(Base, TimestampMixin):
    """A sub-vendor that Brenk dispatches work to.

    Note: sc_provider_id is nullable — Brenk may track vendors that are not
    represented as Providers in ServiceChannel.
    """

    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sc_provider_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True)
    """Legacy: SC provider id. Not used by current sync flows."""

    sc_user_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True)
    """SC user id (from /v3/odata/users). Set by `sync_vendors_from_sc` —
    when present, this row's identity is synced from SC. NULL means a
    Brenk-only vendor that the user added manually via the dashboard."""

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    raw_data: Mapped[dict | None] = mapped_column(JSONB)

    # Brenk-internal operational fields (added 2026-05-19; not present in SC).
    contact_preference: Mapped[str | None] = mapped_column(String(20))
    """e.g. 'sms', 'call', 'email', 'other' — drives notification UX."""

    payment_terms: Mapped[str | None] = mapped_column(String(100))
    """Free text — 'invoices weekly', 'hourly', 'flat per job', etc."""

    service_area: Mapped[str | None] = mapped_column(String(255))
    """Where the vendor will travel. Free text since the granularity
    varies — 'Austin & San Antonio', 'Anywhere', 'Longview only',
    'Austin metro', etc. Brenk's own service footprint is the Austin
    + San Antonio corridor; defaults are written with that in mind."""

    mobile_app_capable: Mapped[bool | None] = mapped_column(Boolean)
    """Whether the vendor uses CubeSmart's mobile app for check-in /
    GPS tracking. None = unknown."""

    markup_notes: Mapped[str | None] = mapped_column(Text)
    """e.g. 'premium work, run higher markup'."""

    communication_notes: Mapped[str | None] = mapped_column(Text)
    """e.g. 'don't text after 6pm', 'responds slowly'."""

    work_orders: Mapped[list["WorkOrder"]] = relationship(back_populates="assigned_vendor")
    # Vendor skills — the shared job-type taxonomy. Ordered by the taxonomy's
    # own display order for stable response shapes.
    job_types: Mapped[list["JobType"]] = relationship(
        secondary="vendor_job_types",
        order_by="JobType.position",
    )
    # Legacy SC-trade specializations — superseded by `job_types`. Kept so the
    # one-time remap can read the old tags; no longer surfaced in the API.
    trade_specializations: Mapped[list["Trade"]] = relationship(
        secondary="vendor_trades",
        order_by="Trade.name",
    )

    def __repr__(self) -> str:
        return f"<Vendor {self.name}>"


class WoVendorAssignment(Base, TimestampMixin):
    """A sub-vendor assigned to a work order.

    Replaces the single `work_orders.assigned_vendor_id` with a many-to-many
    so one job can be split across vendors (e.g. locksmith + electrician).
    `assigned_vendor_id` is kept in sync as the "primary" (first) vendor for
    back-compat. `notified_at` is per-vendor; per-vendor payout fields land in
    a later phase.
    """

    __tablename__ = "wo_vendor_assignments"
    __table_args__ = (UniqueConstraint("work_order_id", "vendor_id", name="uq_wo_vendor"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    work_order_id: Mapped[int] = mapped_column(
        ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vendor_id: Mapped[int] = mapped_column(
        ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Which aspect/skill this vendor covers on the job (optional).
    job_type_id: Mapped[int | None] = mapped_column(ForeignKey("job_types.id"))
    # When Brenk reached THIS vendor (per-vendor notify milestone).
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # What Brenk pays THIS vendor — Brenk-confidential, never sent to SC. The
    # WO-level brenk_labor_cost/brenk_material_cost are kept as the rollup sum.
    labor_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    material_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    # When Brenk paid THIS sub-vendor (drives the payables view).
    paid_to_vendor_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text)

    vendor: Mapped["Vendor"] = relationship()
    job_type: Mapped["JobType | None"] = relationship()

    def __repr__(self) -> str:
        return f"<WoVendorAssignment wo={self.work_order_id} vendor={self.vendor_id}>"


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
    sc_work_order_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
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

    # Brenk-internal invoice fields (added 2026-05-21). These don't
    # exist in SC — they're what we track ourselves to replace Sue's
    # clipboard pile.
    #
    # PRIVACY: vendor cost (labor + material), markup, and the
    # derived total are **Brenk-confidential**. They never leave our
    # database — not in API responses to external systems, not in
    # invoices pushed to SC. SC only ever sees the final total-bill
    # number Daryl manually enters into SC's own invoice form (which
    # is the public-facing bill to the client). NTE (already on this
    # row) is the client-side ceiling we can't exceed.
    #
    # Total bill = (labor_cost + material_cost) * (1 + markup/100)
    # Must be ≤ NTE.
    #
    # Why labor + material separately, not one combined number:
    #   Phase 4 analytics want to see where the money's going. A trade
    #   that's 70% materials needs a different markup strategy than
    #   one that's 70% labor. Stored separately so we don't lose the
    #   distinction at entry time; combined arithmetically when needed.
    brenk_labor_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    brenk_material_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    brenk_markup_percent: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    # Directly-entered, pre-tax total bill — Daryl's escape hatch for
    # when he just knows the number he's charging and doesn't want to
    # break out vendor labor/material + markup. When set, this is the
    # source of truth for the (pre-tax) total bill: the derived
    # cost*(1+markup) calc is bypassed and the markup % is left unknown.
    # Same units as the cost-derived total (8.25% TX sales tax is added
    # at invoice-submit time, not stored here). Mutually exclusive with
    # the cost/markup path in practice — entering vendor costs converts
    # it back to a real markup. Brenk-confidential — never pushed to SC
    # as a breakdown; only the final total reaches the client invoice.
    brenk_total_override: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    brenk_marked_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    brenk_paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Brenk-internal pipeline milestone: when Daryl notified (texted/
    # called) the assigned sub-vendor about this WO. Tracks the
    # "assigned in our heads but never actually told them" failure
    # mode. Null = not yet notified. SC has no equivalent.
    brenk_vendor_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Brenk job category (AI-inferred, then confirmed/overridden by the
    # operator). Distinct from SC's `trade` and `category` — a `JobType` name
    # from the shared `job_types` taxonomy, used for profit metrics, markup
    # suggestions, and vendor matching. `brenk_category` is the effective
    # value; `*_source` is
    # 'ai' (unreviewed), 'confirmed' (operator agreed) or 'manual' (operator
    # changed it); `*_confidence` is the model's 0..1 score; `*_ai` preserves
    # the original AI guess even after a manual override (to measure accuracy).
    brenk_category: Mapped[str | None] = mapped_column(String(50), index=True)
    brenk_category_source: Mapped[str | None] = mapped_column(String(20))
    brenk_category_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    brenk_category_ai: Mapped[str | None] = mapped_column(String(50))
    brenk_category_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # ServiceChannel invoice state, synced from SC invoice webhooks
    # (see docs/architecture/sc-invoice-webhook-sync.md). These let the
    # invoice queue derive Sent -> Approved -> Paid from SC instead of
    # relying solely on the manual "Mark paid" button.
    sc_invoice_id: Mapped[int | None] = mapped_column(BigInteger)
    sc_invoice_number: Mapped[str | None] = mapped_column(String(100))
    sc_invoice_status: Mapped[str | None] = mapped_column(String(40))
    # Amount actually invoiced to the client per SC (vs Brenk's internal
    # computed total). Synced from the invoice's InvoiceTotal.
    sc_invoice_total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    sc_invoice_submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sc_invoice_last_error: Mapped[str | None] = mapped_column(Text)
    # SC-derived paid timestamp (from an InvoicePaid event). brenk_paid_at
    # stays the manual override; we also populate it from here when it's
    # empty so the existing Paid-tab/queue logic works without a refactor.
    sc_paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

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
    # Multi-vendor assignments (the junction). `assigned_vendor_id` above is
    # kept in sync as the primary (first) for back-compat with single-vendor
    # readers.
    vendor_assignments: Mapped[list["WoVendorAssignment"]] = relationship(
        cascade="all, delete-orphan",
        order_by="WoVendorAssignment.created_at",
    )
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
        return (
            f"<StatusHistory wo={self.work_order_id} {self.primary_status}/{self.extended_status}>"
        )
