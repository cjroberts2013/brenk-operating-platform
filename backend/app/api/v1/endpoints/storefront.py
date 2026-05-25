"""Storefront endpoints.

Two routers in one module, mounted separately by `app.api.v1.__init__`:

- `public_router` — `GET /storefront`. **No auth.** Serves the
  marketing site at the bare domain (`brenkfacilityservices.com`).
- `admin_router` — `PATCH /storefront`, `PUT /storefront/services`.
  Authenticated. Mounted under the standard `api_router` so
  Supabase JWT auth applies.

The content table is treated as a **singleton** — there's always
exactly one row with `id = 1`. The GET endpoint auto-creates it
on first call if missing (so a fresh database still serves valid
JSON to the public site). PATCH operates on the same singleton.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_async_db
from app.models.storefront import StorefrontContent, StorefrontService
from app.schemas.storefront import (
    StorefrontResponse,
    StorefrontServicesReplace,
    StorefrontUpdate,
)

public_router = APIRouter()
admin_router = APIRouter()


SINGLETON_ID = 1


async def _fetch_content(
    db: AsyncSession, *, populate_existing: bool = False
) -> StorefrontContent:
    """Fetch the singleton row with services eagerly loaded.

    `populate_existing=True` after a commit forces SQLAlchemy to
    rebuild the in-memory object from the SELECT instead of
    returning the identity-map cached one — necessary because the
    `updated_at` server-onupdate value lives only in the DB until
    we re-select. Same pattern as the WO PATCH handler.
    """
    stmt = (
        select(StorefrontContent)
        .options(selectinload(StorefrontContent.services))
        .where(StorefrontContent.id == SINGLETON_ID)
    )
    if populate_existing:
        stmt = stmt.execution_options(populate_existing=True)
    return (await db.execute(stmt)).scalar_one()


async def _get_or_create_content(db: AsyncSession) -> StorefrontContent:
    """Fetch the singleton row, creating it if it doesn't exist yet.

    The public storefront page hits this endpoint on every request,
    so a fresh database (one before the first editor save) should
    still respond with valid JSON — all nullable fields just come
    back as null. The frontend renderer handles missing fields.
    """
    stmt = (
        select(StorefrontContent)
        .options(selectinload(StorefrontContent.services))
        .where(StorefrontContent.id == SINGLETON_ID)
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        row = StorefrontContent(id=SINGLETON_ID)
        db.add(row)
        await db.commit()
        row = await _fetch_content(db, populate_existing=True)
    return row


@public_router.get("/", response_model=StorefrontResponse)
async def get_storefront(
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> StorefrontResponse:
    """Public — returns the current storefront content + services.

    Both the dashboard editor (initial form values) and the public
    marketing site consume this. No auth; the page is meant to be
    crawlable.
    """
    content = await _get_or_create_content(db)
    return StorefrontResponse.model_validate(content)


@admin_router.patch("/", response_model=StorefrontResponse)
async def update_storefront(
    payload: StorefrontUpdate,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> StorefrontResponse:
    """Authenticated — partial update of page-level content fields.

    Omit a field to leave it alone; set to `null` to clear. Same
    "absent vs explicit-null" handling as the WO PATCH — Pydantic's
    `model_fields_set` is the discriminator.
    """
    content = await _get_or_create_content(db)
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(content, field, value)
    await db.commit()
    # Re-select with populate_existing so the server-side onupdate
    # `updated_at` value comes back live (Pydantic's model_validate
    # would otherwise lazy-load it and fail across async contexts).
    fresh = await _fetch_content(db, populate_existing=True)
    return StorefrontResponse.model_validate(fresh)


@admin_router.put("/services", response_model=StorefrontResponse)
async def replace_services(
    payload: StorefrontServicesReplace,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> StorefrontResponse:
    """Authenticated — replaces the entire services list.

    Editor sends the full desired list on every save. We delete +
    re-insert via cascade rather than diffing — simpler and at
    list sizes <20 the row churn doesn't matter.
    """
    content = await _get_or_create_content(db)

    # Wipe existing — cascade isn't going to fire on a relationship
    # `clear()` without flush, so we delete by setting the list to
    # empty and let SQLAlchemy's delete-orphan cascade do the work.
    content.services = []
    await db.flush()

    # Re-insert from the payload, preserving the client's sort_order.
    for item in payload.services:
        content.services.append(
            StorefrontService(
                content_id=content.id,
                sort_order=item.sort_order,
                title=item.title,
                description=item.description,
                icon=item.icon,
            )
        )
    await db.commit()
    fresh = await _fetch_content(db, populate_existing=True)
    return StorefrontResponse.model_validate(fresh)
