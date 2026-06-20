"""Pydantic response schemas for the work-order API.

ORM mode is enabled (`from_attributes=True`) so we can pass SQLAlchemy
instances directly to these models.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class _OrmModel(BaseModel):
    """Shared base that opts every schema into reading from ORM attributes."""

    model_config = ConfigDict(from_attributes=True)


class ClientRef(_OrmModel):
    """Minimal client info for embedding in WO responses."""

    id: int
    sc_subscriber_id: int
    name: str
    short_name: str | None


class LocationRef(_OrmModel):
    """Minimal location info for embedding in WO responses."""

    id: int
    sc_location_id: int
    store_id: str | None
    name: str | None


class TradeRef(_OrmModel):
    id: int
    sc_trade_id: int | None
    name: str
    # Per-trade default markup %. Surfaced inline on the invoice
    # detail as a suggestion (never auto-applied). Null = no default
    # configured for this trade yet.
    default_markup_percent: Decimal | None = None


class VendorRef(_OrmModel):
    id: int
    sc_provider_id: int | None
    name: str


class InvoiceSummary(_OrmModel):
    """A ServiceChannel invoice record (synced from SC invoice webhooks).

    Surfaced on the WO detail so the full invoice is visible: number,
    status, the client-billed amounts, and the lifecycle dates.
    """

    sc_invoice_id: int | None
    invoice_number: str
    status: str | None
    currency: str | None
    subtotal: Decimal | None
    invoice_tax: Decimal | None
    invoice_total: Decimal | None
    approval_code: str | None
    batch_number: str | None
    comments: str | None
    trade: str | None
    category: str | None
    invoice_date: datetime | None
    posted_date: datetime | None
    approved_date: datetime | None
    paid_date: datetime | None
    last_action_date: datetime | None
    sc_updated_date: datetime | None
    source: str


class InvoiceListItem(InvoiceSummary):
    """An invoice row for the invoice list, plus the linked WO for context
    + navigation. work_order_id is the internal id (for the WO detail
    link); wo_number is the SC work order number."""

    work_order_id: int | None = None
    wo_number: str | None = None
    location_name: str | None = None
    location_store_id: str | None = None


class InvoiceListResponse(BaseModel):
    """Paginated list of actual SC invoices."""

    items: list[InvoiceListItem]
    total: int
    page: int
    page_size: int


class InvoiceSubmitPreview(BaseModel):
    """Server-computed preview of what POST /v3/invoices would send.

    The confirm dialog renders this verbatim — what Daryl approves is
    exactly what goes to SC. `problems` non-empty = not submittable
    (a missing-resolution problem clears once the dialog supplies text).
    """

    eligible: bool
    problems: list[str]
    invoice_number: str
    labor_amount: Decimal
    material_amount: Decimal
    subtotal: Decimal
    tax_amount: Decimal  # 8.25% TX sales tax, matching Daryl's real invoices
    invoice_total: Decimal  # subtotal + tax; must be <= NTE
    nte: Decimal | None
    resolution_text: str | None


class InvoiceSubmitRequest(BaseModel):
    """Body for POST /work-orders/{id}/submit-invoice. `invoice_text`
    overrides/supplies the WO resolution as SC's InvoiceText."""

    invoice_text: str | None = None


class WorkOrderSummary(_OrmModel):
    """A trimmed work-order shape suitable for list views and tables."""

    id: int
    sc_work_order_id: int
    sc_number: str
    primary_status: str
    extended_status: str | None
    priority: str | None
    trade: TradeRef | None
    location: LocationRef | None
    client: ClientRef | None
    assigned_vendor: VendorRef | None
    nte: Decimal | None
    scheduled_date: datetime | None
    sc_updated_date: datetime | None
    # Surfaced here so the invoice-queue tabs can render vendor cost
    # + markup + paid-at inline without a per-row detail fetch.
    # Vendor cost is tracked as labor + material separately for
    # Phase 4 analytics (where the money's going). Total vendor cost
    # is the sum; the markup applies to that sum. Brenk-confidential —
    # see the model docstring.
    brenk_labor_cost: Decimal | None
    brenk_material_cost: Decimal | None
    brenk_markup_percent: Decimal | None
    brenk_total_override: Decimal | None
    brenk_marked_up_at: datetime | None
    brenk_paid_at: datetime | None
    brenk_vendor_notified_at: datetime | None

    # Computed by the list endpoint (not an ORM column): is this WO
    # sitting in its stage past the dashboard's stuck threshold? Lets
    # the list flag stalled rows inline. Defaults False; set per row
    # after model_validate.
    is_stuck: bool = False

    # ServiceChannel invoice state, synced from SC webhooks. Lets the
    # invoice queue show the real invoice number / status / billed total
    # inline on the post-submit tabs.
    sc_invoice_number: str | None
    sc_invoice_status: str | None
    sc_invoice_total: Decimal | None
    sc_invoice_submitted_at: datetime | None
    sc_invoice_last_error: str | None
    sc_paid_at: datetime | None


class WorkOrderDetail(_OrmModel):
    """Full work-order detail. Used by the single-WO endpoint."""

    id: int
    sc_work_order_id: int
    sc_number: str
    sc_purchase_number: str | None

    client: ClientRef | None
    location: LocationRef | None
    trade: TradeRef | None
    assigned_vendor: VendorRef | None

    primary_status: str
    extended_status: str | None
    can_create_invoice: bool

    category: str | None
    sc_category_id: int | None
    priority: str | None
    problem_code: str | None

    description: str | None
    resolution: str | None
    caller: str | None
    approval_code: str | None

    nte: Decimal | None
    currency_code: str

    call_date: datetime | None
    scheduled_date: datetime | None
    expiration_date: datetime | None
    original_eta: datetime | None
    sc_updated_date: datetime | None
    completed_date: datetime | None

    is_invoiced: bool
    is_expired: bool
    is_check_in_denied: bool
    has_work_activity: bool
    auto_complete: bool
    auto_invoice: bool

    # Brenk-internal invoice fields. Labor + material are tracked
    # separately for analytics — vendor sends a bill that breaks them
    # out, we preserve the breakdown. Total vendor cost is the sum
    # (computed on the fly, not stored). Distinct from `nte` above:
    # NTE is the client-side ceiling on what Brenk can bill, the
    # vendor costs are Brenk's internal cost basis for markup.
    # **Brenk-confidential** — never pushed to SC. See model docstring.
    # `brenk_markup_percent` is the actual % Daryl chose (the trade
    # default is just a suggestion). `brenk_marked_up_at` is auto-
    # stamped when the markup is first set; `brenk_paid_at` is the
    # manual "marked paid in our app" timestamp.
    brenk_labor_cost: Decimal | None
    brenk_material_cost: Decimal | None
    brenk_markup_percent: Decimal | None
    # Directly-entered pre-tax total bill (Daryl's "just set the total"
    # path). When set, it's the source of truth for the total and the
    # markup % is unknown. Brenk-confidential.
    brenk_total_override: Decimal | None
    brenk_marked_up_at: datetime | None
    brenk_paid_at: datetime | None
    brenk_vendor_notified_at: datetime | None

    # ServiceChannel invoice state, synced from SC invoice webhooks.
    sc_invoice_id: int | None
    sc_invoice_number: str | None
    sc_invoice_status: str | None
    sc_invoice_total: Decimal | None
    sc_invoice_submitted_at: datetime | None
    sc_invoice_last_error: str | None
    sc_paid_at: datetime | None
    # Full linked SC invoice record(s), latest first. Usually one; more
    # when a WO was re-invoiced (e.g. void then resubmit). Attached by
    # the detail endpoint; defaults empty.
    sc_invoices: list[InvoiceSummary] = []

    notes_count: int
    attachments_count: int

    last_synced_at: datetime
    created_at: datetime
    updated_at: datetime


class WorkOrderListResponse(BaseModel):
    """Paginated list response wrapper."""

    items: list[WorkOrderSummary]
    total: int
    page: int
    page_size: int


class VendorMessage(BaseModel):
    """A ready-to-send vendor notification message for a work order.

    `body` is one plain-text block that pastes into SMS or email; `subject`
    is the suggested email subject. The `to_*`/`contact_preference` fields
    are conveniences for prefilled sms:/mailto: links and (later) auto-send.
    """

    subject: str
    body: str
    to_phone: str | None
    to_email: str | None
    contact_preference: str | None
    photo_count: int


class WorkOrderAttachment(BaseModel):
    """A file attached to a work order (from SC's OData attachments list).

    The raw SC `Uri` (a short-lived presigned SAS URL) is deliberately NOT
    exposed — the browser downloads through our proxy endpoint, which
    resolves a fresh Uri server-side. `content_type` is guessed from the
    file name for client-side icon/preview hints.
    """

    id: int
    name: str | None
    description: str | None
    note_id: int | None
    timestamp: datetime | None
    is_invoice_digital_copy: bool
    upload_by: str | None
    content_type: str | None


class WorkOrderNoteRef(_OrmModel):
    """A note attached to a work order. Returned by /work-orders/{id}/notes."""

    id: int
    sc_note_id: int | None
    note_number: int | None
    note_data: str
    note_type: str | None
    action_required: bool
    is_pinned: bool
    is_attachment_note: bool
    created_by: str | None
    company_name: str | None
    created_at_sc: datetime | None
    source: str
