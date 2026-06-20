"""Pydantic schemas for the locations API.

Locations are SC-sourced (synced from work orders) but carry Brenk
enrichment on top: a district-manager contact, a 3-tier health rating,
running notes, and a history of gate/access codes. The sync never writes
the enrichment fields — see app/services/sync/upserter.py.

`rating` is validated against a closed set here (the model column is a
plain String, matching the rest of the codebase). Address fields are
read out of the location's SC `raw_data` blob by the endpoint rather
than normalized into columns — see LocationDetail.address.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _OrmModel(BaseModel):
    """Shared base that opts every schema into reading from ORM attributes."""

    model_config = ConfigDict(from_attributes=True)


# 3-tier operational health flag. None = unrated.
_RATING = Literal["good", "watch", "problem"]


class GateCodeRead(_OrmModel):
    """A single gate/access code with its lifecycle state."""

    id: int
    label: str | None
    code: str
    is_active: bool
    invalidated_at: datetime | None
    created_at: datetime
    updated_at: datetime


class GateCodeCreate(BaseModel):
    """POST body for adding a new (active) gate code to a location."""

    code: str = Field(min_length=1, max_length=100)
    label: str | None = Field(default=None, max_length=100)


class LocationMetrics(BaseModel):
    """Derived work-order metrics for a location (computed by the endpoint,
    not ORM columns)."""

    total_work_orders: int = 0
    active_work_orders: int = 0
    last_work_order_date: datetime | None = None


class LocationSummary(_OrmModel):
    """List-view shape. Metrics are attached by the list endpoint."""

    id: int
    sc_location_id: int
    store_id: str | None
    name: str | None
    region: str | None
    district: str | None
    rating: str | None
    district_manager_name: str | None

    # Computed by the list endpoint, defaulted so model_validate(orm) works
    # before they're filled in.
    total_work_orders: int = 0
    active_work_orders: int = 0
    last_work_order_date: datetime | None = None


class LocationDetail(_OrmModel):
    """Detail-view shape: full enrichment + address (from raw_data) + the
    location's gate codes split into active vs. history + work-order metrics.
    The location's work orders are fetched separately and paginated via
    GET /locations/{id}/work-orders. Computed fields are attached by the
    endpoint."""

    id: int
    sc_location_id: int
    store_id: str | None
    name: str | None
    region: str | None
    district: str | None
    latitude: Decimal | None
    longitude: Decimal | None

    district_manager_name: str | None
    district_manager_phone: str | None
    district_manager_email: str | None
    rating: str | None
    description: str | None

    # Address pulled from the SC raw_data blob (not a normalized column).
    address: str | None = None

    gate_codes_active: list[GateCodeRead] = []
    gate_codes_history: list[GateCodeRead] = []

    total_work_orders: int = 0
    active_work_orders: int = 0
    last_work_order_date: datetime | None = None

    created_at: datetime
    updated_at: datetime


class LocationUpdate(BaseModel):
    """PATCH body. Brenk enrichment fields only — every field optional, so
    only the keys present in the request are touched (exclude_unset)."""

    district_manager_name: str | None = Field(default=None, max_length=255)
    district_manager_phone: str | None = Field(default=None, max_length=50)
    district_manager_email: str | None = Field(default=None, max_length=255)
    rating: _RATING | None = None
    description: str | None = None


class LocationListResponse(BaseModel):
    items: list[LocationSummary]
    total: int
    page: int
    page_size: int
