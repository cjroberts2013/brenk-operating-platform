"""Pydantic schemas for the vendor API.

Mirrors the expanded Vendor model. `VendorRef` (in `work_order.py`) is
the minimal shape used for embedding inside other responses; the
schemas here cover create / update / detail / list.

`contact_preference` and `payment_terms` are free text for now. The UI
suggests common values via dropdowns, but accepts anything — keeps us
unblocked while Daryl tells us what shapes actually show up.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.work_order import TradeRef


class _OrmModel(BaseModel):
    """Shared base that opts every schema into reading from ORM attributes."""

    model_config = ConfigDict(from_attributes=True)


_CONTACT_PREFERENCE = Literal["sms", "call", "email", "other"]


class VendorBase(BaseModel):
    """Fields common to create + update payloads."""

    name: str = Field(min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    notes: str | None = None
    is_active: bool = True

    contact_preference: _CONTACT_PREFERENCE | None = None
    payment_terms: str | None = Field(default=None, max_length=100)
    mobile_app_capable: bool | None = None
    markup_notes: str | None = None
    communication_notes: str | None = None

    trade_ids: list[int] = Field(
        default_factory=list,
        description="IDs of trades this vendor specializes in",
    )


class VendorCreate(VendorBase):
    """POST body. `name` is the only required field; everything else has
    a sensible default or stays null.
    """


class VendorUpdate(BaseModel):
    """PATCH body. Every field is optional; only the fields present in
    the request are touched.
    """

    name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    notes: str | None = None
    is_active: bool | None = None

    contact_preference: _CONTACT_PREFERENCE | None = None
    payment_terms: str | None = Field(default=None, max_length=100)
    mobile_app_capable: bool | None = None
    markup_notes: str | None = None
    communication_notes: str | None = None

    trade_ids: list[int] | None = Field(
        default=None,
        description="If present, replaces the vendor's trade list entirely",
    )


class VendorSummary(_OrmModel):
    """List-view shape. Adds an `active_work_orders` count alongside the
    profile fields most useful for the table view.
    """

    id: int
    name: str
    phone: str | None
    email: str | None
    is_active: bool
    contact_preference: str | None
    payment_terms: str | None
    mobile_app_capable: bool | None
    active_work_orders: int
    trade_specializations: list[TradeRef]


class VendorDetail(_OrmModel):
    """Detail-view shape. Everything in the model plus a count of how many
    open WOs are assigned to this vendor.
    """

    id: int
    sc_provider_id: int | None
    name: str
    phone: str | None
    email: str | None
    notes: str | None
    is_active: bool

    contact_preference: str | None
    payment_terms: str | None
    mobile_app_capable: bool | None
    markup_notes: str | None
    communication_notes: str | None

    trade_specializations: list[TradeRef]
    active_work_orders: int

    created_at: datetime
    updated_at: datetime


class VendorListResponse(BaseModel):
    items: list[VendorSummary]
    total: int
    page: int
    page_size: int
