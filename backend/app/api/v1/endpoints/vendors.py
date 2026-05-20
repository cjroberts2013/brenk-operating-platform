"""Vendor CRUD endpoints.

Reads + writes go to our local DB; vendors are Brenk-internal data
and intentionally do not propagate to ServiceChannel (Phase 1 scope
decision — see CLAUDE.md "Dashboard Plan").
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_async_db
from app.models.work_order import Trade, Vendor, WorkOrder
from app.schemas.vendor import (
    VendorCreate,
    VendorDetail,
    VendorListResponse,
    VendorSummary,
    VendorUpdate,
)

router = APIRouter()

_TERMINAL_STATUSES = ("COMPLETED", "CANCELLED")
_DEFAULT_PAGE_SIZE = 50
_MAX_PAGE_SIZE = 200


async def _active_counts(
    db: AsyncSession, vendor_ids: list[int]
) -> dict[int, int]:
    """Return {vendor_id: count of non-terminal work orders assigned}.

    One grouped query for the whole batch — keeps the list endpoint
    from issuing N+1 counts.
    """
    if not vendor_ids:
        return {}
    stmt = (
        select(WorkOrder.assigned_vendor_id, func.count(WorkOrder.id))
        .where(
            WorkOrder.assigned_vendor_id.in_(vendor_ids),
            WorkOrder.primary_status.notin_(_TERMINAL_STATUSES),
        )
        .group_by(WorkOrder.assigned_vendor_id)
    )
    rows = (await db.execute(stmt)).all()
    return {row[0]: row[1] for row in rows if row[0] is not None}


async def _load_trades(db: AsyncSession, trade_ids: list[int]) -> list[Trade]:
    """Fetch the given Trade rows, raising 400 if any id is unknown."""
    if not trade_ids:
        return []
    unique_ids = list({*trade_ids})
    rows = (
        await db.execute(select(Trade).where(Trade.id.in_(unique_ids)))
    ).scalars().all()
    found_ids = {t.id for t in rows}
    missing = [tid for tid in unique_ids if tid not in found_ids]
    if missing:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"unknown trade_ids: {missing}",
        )
    return list(rows)


async def _fetch_vendor(db: AsyncSession, vendor_id: int) -> Vendor:
    """Look up a vendor by id with trades eager-loaded, or raise 404."""
    stmt = (
        select(Vendor)
        .options(selectinload(Vendor.trade_specializations))
        .where(Vendor.id == vendor_id)
    )
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
        mobile_app_capable=vendor.mobile_app_capable,
        markup_notes=vendor.markup_notes,
        communication_notes=vendor.communication_notes,
        trade_specializations=vendor.trade_specializations,  # type: ignore[arg-type]
        active_work_orders=active_count,
        created_at=vendor.created_at,
        updated_at=vendor.updated_at,
    )


def _to_summary(vendor: Vendor, active_count: int) -> VendorSummary:
    return VendorSummary(
        id=vendor.id,
        name=vendor.name,
        phone=vendor.phone,
        email=vendor.email,
        notes=vendor.notes,
        is_active=vendor.is_active,
        contact_preference=vendor.contact_preference,
        payment_terms=vendor.payment_terms,
        mobile_app_capable=vendor.mobile_app_capable,
        markup_notes=vendor.markup_notes,
        communication_notes=vendor.communication_notes,
        trade_specializations=vendor.trade_specializations,  # type: ignore[arg-type]
        active_work_orders=active_count,
    )


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------


@router.get("/", response_model=VendorListResponse)
async def list_vendors(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    is_active: Annotated[
        bool | None,
        Query(description="Filter to active or inactive vendors"),
    ] = None,
    trade_id: Annotated[
        int | None,
        Query(description="Filter to vendors specializing in this trade"),
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=_MAX_PAGE_SIZE)
    ] = _DEFAULT_PAGE_SIZE,
) -> VendorListResponse:
    """List vendors, ordered alphabetically by name."""
    filters = []
    if is_active is not None:
        filters.append(Vendor.is_active.is_(is_active))
    if trade_id is not None:
        filters.append(
            Vendor.id.in_(
                select(Vendor.id)
                .join(Vendor.trade_specializations)
                .where(Trade.id == trade_id)
            )
        )

    count_stmt = select(func.count()).select_from(Vendor)
    if filters:
        count_stmt = count_stmt.where(*filters)
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(Vendor)
        .options(selectinload(Vendor.trade_specializations))
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
    trades = await _load_trades(db, payload.trade_ids)

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
    vendor.trade_specializations = trades
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
    trade_ids = update_data.pop("trade_ids", None)

    for field, value in update_data.items():
        setattr(vendor, field, value)

    if trade_ids is not None:
        vendor.trade_specializations = await _load_trades(db, trade_ids)

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
