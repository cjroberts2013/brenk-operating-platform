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


class VendorRef(_OrmModel):
    id: int
    sc_provider_id: int | None
    name: str


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
    nte: Decimal | None
    scheduled_date: datetime | None
    sc_updated_date: datetime | None


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
