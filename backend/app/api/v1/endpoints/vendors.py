"""Vendor CRUD endpoints.

Reads + writes go to our local DB; vendors are Brenk-internal data
and intentionally do not propagate to ServiceChannel (Phase 1 scope
decision — see CLAUDE.md "Dashboard Plan").
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_async_db
from app.models.work_order import JobType, Vendor
from app.schemas.vendor import (
    VendorCreate,
    VendorDetail,
    VendorListResponse,
    VendorSummary,
    VendorUpdate,
)
from app.services.sync.vendors import sync_vendors_from_sc
from app.services.workload import active_work_order_counts as _active_counts


class VendorSyncSummary(BaseModel):
    """Result of POST /api/v1/vendors/sync."""

    fetched: int
    created: int
    updated: int
    errors: int


router = APIRouter()

_DEFAULT_PAGE_SIZE = 50
_MAX_PAGE_SIZE = 200


async def _load_job_types(db: AsyncSession, job_type_ids: list[int]) -> list[JobType]:
    """Fetch the given JobType rows, raising 400 if any id is unknown."""
    if not job_type_ids:
        return []
    unique_ids = list({*job_type_ids})
    rows = (await db.execute(select(JobType).where(JobType.id.in_(unique_ids)))).scalars().all()
    found_ids = {t.id for t in rows}
    missing = [tid for tid in unique_ids if tid not in found_ids]
    if missing:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"unknown job_type_ids: {missing}",
        )
    return list(rows)


async def _fetch_vendor(db: AsyncSession, vendor_id: int) -> Vendor:
    """Look up a vendor by id with skills eager-loaded, or raise 404."""
    stmt = select(Vendor).options(selectinload(Vendor.job_types)).where(Vendor.id == vendor_id)
    vendor = (await db.execute(stmt)).scalar_one_or_none()
    if vendor is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"vendor {vendor_id} not found",
        )
    return vendor


def _to_detail(vendor: Vendor, active_count: int) -> VendorDetail:
    """Serialize a Vendor + computed active count into the response shape."""
    return VendorDetail(
        id=vendor.id,
        sc_provider_id=vendor.sc_provider_id,
        name=vendor.name,
        phone=vendor.phone,
        email=vendor.email,
        notes=vendor.notes,
        is_active=vendor.is_active,
        contact_preference=vendor.contact_preference,
        payment_terms=vendor.payment_terms,
        service_area=vendor.service_area,
        mobile_app_capable=vendor.mobile_app_capable,
        markup_notes=vendor.markup_notes,
        communication_notes=vendor.communication_notes,
        skills=vendor.job_types,  # type: ignore[arg-type]
        active_work_orders=active_count,
        created_at=vendor.created_at,
        updated_at=vendor.updated_at,
    )


def _to_summary(vendor: Vendor, active_count: int) -> VendorSummary:
    return VendorSummary.from_vendor(vendor, active_count)


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------


@router.post("/sync", response_model=VendorSyncSummary)
async def sync_vendors_endpoint() -> VendorSyncSummary:
    """Trigger a one-way sync from SC's user catalog into our vendors
    table. Brenk-internal fields are preserved. Safe to call repeatedly.
    """
    summary = await sync_vendors_from_sc()
    return VendorSyncSummary(
        fetched=summary["fetched"],
        created=summary["created"],
        updated=summary["updated"],
        errors=len(summary["errors"]),
    )


@router.get("/", response_model=VendorListResponse)
async def list_vendors(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    is_active: Annotated[
        bool | None,
        Query(description="Filter to active or inactive vendors"),
    ] = None,
    job_type_id: Annotated[
        int | None,
        Query(description="Filter to vendors who do this job type (skill)"),
    ] = None,
    q: Annotated[
        str | None,
        Query(
            description=(
                "Free-text search across name, phone, email, service area, "
                "and skill name. Case-insensitive, substring match."
            ),
        ),
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=_MAX_PAGE_SIZE)] = _DEFAULT_PAGE_SIZE,
) -> VendorListResponse:
    """List vendors, ordered alphabetically by name."""
    filters = []
    if is_active is not None:
        filters.append(Vendor.is_active.is_(is_active))
    if job_type_id is not None:
        filters.append(
            Vendor.id.in_(select(Vendor.id).join(Vendor.job_types).where(JobType.id == job_type_id))
        )
    if q is not None and q.strip():
        needle = f"%{q.strip()}%"
        # Vendor.id IN (vendors who match by their own field OR by a skill
        # name). Done as a subquery so the outer paginated query doesn't
        # grow rows per skill-match.
        skill_match_ids = select(Vendor.id).join(Vendor.job_types).where(JobType.name.ilike(needle))
        filters.append(
            or_(
                Vendor.name.ilike(needle),
                Vendor.phone.ilike(needle),
                Vendor.email.ilike(needle),
                Vendor.service_area.ilike(needle),
                Vendor.id.in_(skill_match_ids),
            )
        )

    count_stmt = select(func.count()).select_from(Vendor)
    if filters:
        count_stmt = count_stmt.where(*filters)
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(Vendor)
        .options(selectinload(Vendor.job_types))
        .order_by(Vendor.name.asc(), Vendor.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    if filters:
        stmt = stmt.where(*filters)
    vendors = list((await db.execute(stmt)).scalars().all())

    counts = await _active_counts(db, [v.id for v in vendors])
    return VendorListResponse(
        items=[_to_summary(v, counts.get(v.id, 0)) for v in vendors],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{vendor_id}", response_model=VendorDetail)
async def get_vendor(
    vendor_id: int,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> VendorDetail:
    vendor = await _fetch_vendor(db, vendor_id)
    counts = await _active_counts(db, [vendor.id])
    return _to_detail(vendor, counts.get(vendor.id, 0))


@router.post(
    "/",
    response_model=VendorDetail,
    status_code=http_status.HTTP_201_CREATED,
)
async def create_vendor(
    payload: VendorCreate,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> VendorDetail:
    job_types = await _load_job_types(db, payload.job_type_ids)

    vendor = Vendor(
        name=payload.name,
        phone=payload.phone,
        email=payload.email,
        notes=payload.notes,
        is_active=payload.is_active,
        contact_preference=payload.contact_preference,
        payment_terms=payload.payment_terms,
        mobile_app_capable=payload.mobile_app_capable,
        markup_notes=payload.markup_notes,
        communication_notes=payload.communication_notes,
    )
    vendor.job_types = job_types
    db.add(vendor)
    await db.commit()
    # Re-fetch with eager-loaded relationships. Avoids the MissingGreenlet
    # that can fire when Pydantic touches an expired attribute mid-serialize.
    fresh = await _fetch_vendor(db, vendor.id)
    return _to_detail(fresh, 0)


@router.patch("/{vendor_id}", response_model=VendorDetail)
async def update_vendor(
    vendor_id: int,
    payload: VendorUpdate,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> VendorDetail:
    vendor = await _fetch_vendor(db, vendor_id)

    # `exclude_unset=True` so PATCH only touches fields the client sent.
    update_data = payload.model_dump(exclude_unset=True)
    job_type_ids = update_data.pop("job_type_ids", None)

    for field, value in update_data.items():
        setattr(vendor, field, value)

    if job_type_ids is not None:
        vendor.job_types = await _load_job_types(db, job_type_ids)

    await db.commit()
    fresh = await _fetch_vendor(db, vendor.id)
    counts = await _active_counts(db, [fresh.id])
    return _to_detail(fresh, counts.get(fresh.id, 0))


@router.delete("/{vendor_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_vendor(
    vendor_id: int,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> None:
    """Soft-delete: mark the vendor inactive. We never hard-delete because
    work orders may reference this vendor historically; we want those
    references to stay intact.
    """
    vendor = await _fetch_vendor(db, vendor_id)
    vendor.is_active = False
    await db.commit()
