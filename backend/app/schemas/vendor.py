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

from app.schemas.job_type import JobTypeRef


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
    service_area: str | None = Field(default=None, max_length=255)
    mobile_app_capable: bool | None = None
    markup_notes: str | None = None
    communication_notes: str | None = None

    job_type_ids: list[int] = Field(
        default_factory=list,
        description="IDs of job types (skills) this vendor does",
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
    service_area: str | None = Field(default=None, max_length=255)
    mobile_app_capable: bool | None = None
    markup_notes: str | None = None
    communication_notes: str | None = None

    job_type_ids: list[int] | None = Field(
        default=None,
        description="If present, replaces the vendor's skill list entirely",
    )


class VendorSummary(_OrmModel):
    """List-view shape. Carries enough fields that the Edit modal can
    pre-fill without a separate detail fetch (the textarea fields and
    other secondary text are small enough that it's worth the extra
    bytes).
    """

    id: int
    name: str
    phone: str | None
    email: str | None
    notes: str | None
    is_active: bool
    contact_preference: str | None
    payment_terms: str | None
    service_area: str | None
    mobile_app_capable: bool | None
    markup_notes: str | None
    communication_notes: str | None
    active_work_orders: int
    skills: list[JobTypeRef]

    @classmethod
    def from_vendor(cls, vendor: object, active_count: int) -> "VendorSummary":
        """Build a summary from a Vendor ORM row + its (separately computed)
        open-WO count. Shared by the vendors list and the suggestion service
        so the field mapping lives in exactly one place."""
        return cls(
            id=vendor.id,  # type: ignore[attr-defined]
            name=vendor.name,  # type: ignore[attr-defined]
            phone=vendor.phone,  # type: ignore[attr-defined]
            email=vendor.email,  # type: ignore[attr-defined]
            notes=vendor.notes,  # type: ignore[attr-defined]
            is_active=vendor.is_active,  # type: ignore[attr-defined]
            contact_preference=vendor.contact_preference,  # type: ignore[attr-defined]
            payment_terms=vendor.payment_terms,  # type: ignore[attr-defined]
            service_area=vendor.service_area,  # type: ignore[attr-defined]
            mobile_app_capable=vendor.mobile_app_capable,  # type: ignore[attr-defined]
            markup_notes=vendor.markup_notes,  # type: ignore[attr-defined]
            communication_notes=vendor.communication_notes,  # type: ignore[attr-defined]
            skills=vendor.job_types,  # type: ignore[attr-defined]
            active_work_orders=active_count,
        )


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
    service_area: str | None
    mobile_app_capable: bool | None
    markup_notes: str | None
    communication_notes: str | None

    skills: list[JobTypeRef]
    active_work_orders: int

    created_at: datetime
    updated_at: datetime


class VendorListResponse(BaseModel):
    items: list[VendorSummary]
    total: int
    page: int
    page_size: int


# -----------------------------------------------------------------------------
# Vendor suggestions (assign-step recommendations)
# -----------------------------------------------------------------------------


class VendorSuggestionAxis(BaseModel):
    """One scoring axis (trade / location / workload) with a human reason."""

    score: float
    reason: str


class VendorSuggestion(BaseModel):
    """A scored vendor for a work order, with a per-axis breakdown and a
    composed one-line reason ("Does Electrical · covers Austin · 1 active job").
    """

    vendor: VendorSummary
    composite_score: float
    trade: VendorSuggestionAxis
    location: VendorSuggestionAxis
    workload: VendorSuggestionAxis
    reason: str
    # This vendor is already assigned to the WO (kept in `ranked`, excluded
    # from `top_pick`).
    is_current: bool


class VendorSuggestionResponse(BaseModel):
    """Ranked vendor suggestions for one work order's assign step."""

    # Best non-current candidate, only when it clears the strong-match
    # threshold; null → the UI degrades to the manual dropdown.
    top_pick: VendorSuggestion | None
    # All trade-eligible vendors, best-first (includes the current one, flagged).
    ranked: list[VendorSuggestion]
    # The WO had a known trade, so the trade gate was applied.
    has_trade: bool
    # The WO's city, echoed for transparency in the UI.
    wo_city: str | None
