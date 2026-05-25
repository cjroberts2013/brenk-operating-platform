"""Pydantic schemas for the storefront API.

Three shapes:
- `StorefrontResponse` — the read shape returned by `GET /storefront`.
  Public; serves both the dashboard editor (initial load) and the
  public marketing site renderer.
- `StorefrontUpdate` — partial PATCH body for editing page-level
  fields. All fields optional; omitted fields aren't touched.
- `StorefrontServicesReplace` — full replacement of the services
  list (the editor sends the whole array on save, which is simpler
  than per-row CRUD for a list of ~5-20 items).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class _OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class StorefrontServiceRef(_OrmModel):
    """One service item — read and write share the same shape since
    the editor replaces the list wholesale."""

    id: int | None = None
    """Set on read; ignored on write (server generates new ids on
    replace, so client-supplied ids are not honored)."""
    sort_order: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=120)
    description: str | None = None
    icon: str | None = Field(default=None, max_length=50)


class StorefrontResponse(_OrmModel):
    """Read shape — both editor and public renderer consume this."""

    id: int

    hero_title: str | None
    hero_subtitle: str | None
    hero_cta_text: str | None
    hero_cta_link: str | None
    hero_image_url: str | None

    about_heading: str | None
    about_body: str | None
    about_image_url: str | None

    service_area_heading: str | None
    service_area_body: str | None

    contact_email: str | None
    contact_phone: str | None
    contact_address: str | None
    contact_hours: str | None

    footer_tagline: str | None
    footer_copyright: str | None

    logo_url: str | None

    services: list[StorefrontServiceRef]

    created_at: datetime
    updated_at: datetime


class StorefrontUpdate(BaseModel):
    """PATCH body. Omit a field to leave it alone; set to null to
    clear it. We use `model_fields_set` in the endpoint to tell
    "absent" from "null" — same pattern as the WO PATCH."""

    hero_title: str | None = Field(default=None, max_length=200)
    hero_subtitle: str | None = Field(default=None, max_length=500)
    hero_cta_text: str | None = Field(default=None, max_length=100)
    hero_cta_link: str | None = Field(default=None, max_length=500)
    hero_image_url: str | None = Field(default=None, max_length=1000)

    about_heading: str | None = Field(default=None, max_length=200)
    about_body: str | None = None
    about_image_url: str | None = Field(default=None, max_length=1000)

    service_area_heading: str | None = Field(default=None, max_length=200)
    service_area_body: str | None = None

    contact_email: str | None = Field(default=None, max_length=255)
    contact_phone: str | None = Field(default=None, max_length=50)
    contact_address: str | None = Field(default=None, max_length=500)
    contact_hours: str | None = Field(default=None, max_length=200)

    footer_tagline: str | None = Field(default=None, max_length=300)
    footer_copyright: str | None = Field(default=None, max_length=200)

    logo_url: str | None = Field(default=None, max_length=1000)


class StorefrontServicesReplace(BaseModel):
    """PUT body — replaces the entire services list. Simpler than
    per-row CRUD for a list this size; the editor sends the full
    desired state on every save."""

    services: list[StorefrontServiceRef]
