"""Location endpoints.

Locations are synced from ServiceChannel work orders (read-only as far as
SC data goes — there is no manual create). Brenk layers operational
enrichment on top: a district-manager contact, a 3-tier health rating, a
running description, and a history of gate/access codes.

Endpoints:
- GET  /locations/                         paginated list + ?q= + ?rating=
- GET  /locations/{id}                     detail + related WOs + metrics
- PATCH /locations/{id}                    edit Brenk enrichment fields
- POST /locations/{id}/gate-codes          add an active gate code
- POST /locations/{id}/gate-codes/{cid}/invalidate   retire a gate code

No POST-create / DELETE for locations — they come from sync.
"""

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi import status as http_status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_async_db
from app.models.work_order import GateCode, Location, WorkOrder, WoVendorAssignment
from app.schemas.location import (
    GateCodeCreate,
    GateCodeRead,
    LocationDetail,
    LocationListResponse,
    LocationSummary,
    LocationUpdate,
)
from app.schemas.work_order import WorkOrderListResponse, WorkOrderSummary
from app.services.addresses import format_address
from app.services.location_export import (
    XLSX_MEDIA_TYPE,
    build_locations_workbook,
)
from app.services.pipeline import classify, is_stuck

router = APIRouter()

_TERMINAL_STATUSES = ("COMPLETED", "CANCELLED")
_DEFAULT_PAGE_SIZE = 50
_MAX_PAGE_SIZE = 200
# Related work orders on the detail page are paginated (no cap) — a
# long-lived store can accumulate many WOs over the years.
_DEFAULT_WO_PAGE_SIZE = 20


async def _location_metrics(db: AsyncSession, location_ids: list[int]) -> dict[int, dict[str, Any]]:
    """{location_id: {total_work_orders, active_work_orders, last_work_order_date}}.

    One grouped query for the whole batch — keeps the list endpoint from
    issuing N+1 counts (mirrors vendors._active_counts).
    """
    if not location_ids:
        return {}
    stmt = (
        select(
            WorkOrder.location_id,
            func.count(WorkOrder.id).label("total"),
            func.count(WorkOrder.id)
            .filter(WorkOrder.primary_status.notin_(_TERMINAL_STATUSES))
            .label("active"),
            func.max(func.coalesce(WorkOrder.completed_date, WorkOrder.sc_updated_date)).label(
                "last_wo_date"
            ),
        )
        .where(WorkOrder.location_id.in_(location_ids))
        .group_by(WorkOrder.location_id)
    )
    rows = (await db.execute(stmt)).all()
    return {
        row.location_id: {
            "total_work_orders": row.total,
            "active_work_orders": row.active,
            "last_work_order_date": row.last_wo_date,
        }
        for row in rows
        if row.location_id is not None
    }


async def _fetch_location(db: AsyncSession, location_id: int) -> Location:
    """Look up a location by id with gate codes eager-loaded, or raise 404."""
    stmt = (
        select(Location)
        .options(selectinload(Location.gate_codes))
        .where(Location.id == location_id)
    )
    location = (await db.execute(stmt)).scalar_one_or_none()
    if location is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"location {location_id} not found",
        )
    return location


def _build_detail(location: Location, metrics: dict[str, Any]) -> LocationDetail:
    """Serialize a Location (+ computed pieces) into the detail response.

    Built explicitly rather than via model_validate(location) so we never
    touch the `work_orders` ORM relationship (lazy-load → MissingGreenlet in
    async). The location's work orders are served, paginated, by
    list_location_work_orders.
    """
    active = [gc for gc in location.gate_codes if gc.is_active]
    history = [gc for gc in location.gate_codes if not gc.is_active]
    return LocationDetail(
        id=location.id,
        sc_location_id=location.sc_location_id,
        store_id=location.store_id,
        name=location.name,
        region=location.region,
        district=location.district,
        latitude=location.latitude,
        longitude=location.longitude,
        district_manager_name=location.district_manager_name,
        district_manager_phone=location.district_manager_phone,
        district_manager_email=location.district_manager_email,
        rating=location.rating,
        description=location.description,
        address=format_address(location.raw_data),
        gate_codes_active=[GateCodeRead.model_validate(gc) for gc in active],
        gate_codes_history=[GateCodeRead.model_validate(gc) for gc in history],
        total_work_orders=metrics.get("total_work_orders", 0),
        active_work_orders=metrics.get("active_work_orders", 0),
        last_work_order_date=metrics.get("last_work_order_date"),
        created_at=location.created_at,
        updated_at=location.updated_at,
    )


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------


@router.get("/", response_model=LocationListResponse)
async def list_locations(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    q: Annotated[
        str | None,
        Query(
            description=(
                "Free-text search across name, store id, region, district, and "
                "district manager name. Case-insensitive, substring match."
            ),
        ),
    ] = None,
    rating: Annotated[
        str | None,
        Query(description="Filter to locations with this rating (good/watch/problem)"),
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=_MAX_PAGE_SIZE)] = _DEFAULT_PAGE_SIZE,
) -> LocationListResponse:
    """List locations, ordered by store id then name."""
    filters = []
    if rating is not None:
        filters.append(Location.rating == rating)
    if q is not None and q.strip():
        needle = f"%{q.strip()}%"
        filters.append(
            or_(
                Location.name.ilike(needle),
                Location.store_id.ilike(needle),
                Location.region.ilike(needle),
                Location.district.ilike(needle),
                Location.district_manager_name.ilike(needle),
            )
        )

    count_stmt = select(func.count()).select_from(Location)
    if filters:
        count_stmt = count_stmt.where(*filters)
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(Location)
        .order_by(Location.store_id.asc().nullslast(), Location.name.asc(), Location.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    if filters:
        stmt = stmt.where(*filters)
    locations = list((await db.execute(stmt)).scalars().all())

    metrics = await _location_metrics(db, [loc.id for loc in locations])
    items: list[LocationSummary] = []
    for loc in locations:
        summary = LocationSummary.model_validate(loc)
        m = metrics.get(loc.id)
        if m:
            summary.total_work_orders = m["total_work_orders"]
            summary.active_work_orders = m["active_work_orders"]
            summary.last_work_order_date = m["last_work_order_date"]
        items.append(summary)

    return LocationListResponse(items=items, total=total, page=page, page_size=page_size)


def _export_row(location: Location) -> dict[str, Any]:
    """Flatten a Location into the export row shape (store #, name, address)."""
    return {
        "store_id": location.store_id,
        "name": location.name,
        "address": format_address(location.raw_data),
    }


# NOTE: this literal route MUST stay above `/{location_id}` — path-param
# routes match by registration order, so `/{location_id}` registered first
# would swallow `/export.xlsx` (and 422 on the int parse).
@router.get("/export.xlsx")
async def export_locations(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    q: Annotated[str | None, Query(description="Same free-text filter as the list.")] = None,
    rating: Annotated[str | None, Query(description="Same rating filter as the list.")] = None,
) -> Response:
    """Download locations as an .xlsx (respecting the q/rating filters).

    No pagination — a full export of what the filters select. Brenk runs
    ~180 facilities, so this is a small, one-shot query.
    """
    filters = []
    if rating is not None:
        filters.append(Location.rating == rating)
    if q is not None and q.strip():
        needle = f"%{q.strip()}%"
        filters.append(
            or_(
                Location.name.ilike(needle),
                Location.store_id.ilike(needle),
                Location.region.ilike(needle),
                Location.district.ilike(needle),
                Location.district_manager_name.ilike(needle),
            )
        )

    stmt = select(Location).order_by(
        Location.store_id.asc().nullslast(), Location.name.asc(), Location.id.asc()
    )
    if filters:
        stmt = stmt.where(*filters)
    locations = list((await db.execute(stmt)).scalars().all())

    rows = [_export_row(loc) for loc in locations]
    content = build_locations_workbook(rows)

    stamp = datetime.now(UTC).strftime("%Y-%m-%d")
    filename = f"brenk-locations-{stamp}.xlsx"
    return Response(
        content=content,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{location_id}", response_model=LocationDetail)
async def get_location(
    location_id: int,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> LocationDetail:
    location = await _fetch_location(db, location_id)
    metrics = (await _location_metrics(db, [location.id])).get(location.id, {})
    return _build_detail(location, metrics)


@router.get("/{location_id}/work-orders", response_model=WorkOrderListResponse)
async def list_location_work_orders(
    location_id: int,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=_MAX_PAGE_SIZE)] = _DEFAULT_WO_PAGE_SIZE,
) -> WorkOrderListResponse:
    """The location's work orders, newest first, paginated (no cap)."""
    # 404 if the location doesn't exist, so the page can distinguish
    # "unknown location" from "location with no work orders".
    await _fetch_location(db, location_id)

    count_stmt = (
        select(func.count(WorkOrder.id))
        .select_from(WorkOrder)
        .where(WorkOrder.location_id == location_id)
    )
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(WorkOrder)
        .options(
            selectinload(WorkOrder.client),
            selectinload(WorkOrder.location),
            selectinload(WorkOrder.trade),
            selectinload(WorkOrder.assigned_vendor),
            selectinload(WorkOrder.vendor_assignments).options(
                selectinload(WoVendorAssignment.vendor),
                selectinload(WoVendorAssignment.job_type),
            ),
        )
        .where(WorkOrder.location_id == location_id)
        .order_by(WorkOrder.sc_updated_date.desc().nullslast(), WorkOrder.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).scalars().all()

    items: list[WorkOrderSummary] = []
    for row in rows:
        summary = WorkOrderSummary.model_validate(row)
        stage_key = classify(
            row.primary_status,
            row.extended_status,
            row.assigned_vendor_id is not None,
        )
        summary.is_stuck = (
            is_stuck(stage_key, row.sc_updated_date)
            if stage_key and row.brenk_sc_deleted_at is None
            else False
        )
        items.append(summary)

    return WorkOrderListResponse(items=items, total=total, page=page, page_size=page_size)


@router.patch("/{location_id}", response_model=LocationDetail)
async def update_location(
    location_id: int,
    payload: LocationUpdate,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> LocationDetail:
    """Edit the Brenk enrichment fields. SC-sourced fields are read-only."""
    location = await _fetch_location(db, location_id)

    # exclude_unset so PATCH only touches the fields the client sent.
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(location, field, value)

    await db.commit()

    fresh = await _fetch_location(db, location_id)
    metrics = (await _location_metrics(db, [fresh.id])).get(fresh.id, {})
    return _build_detail(fresh, metrics)


@router.post(
    "/{location_id}/gate-codes",
    response_model=GateCodeRead,
    status_code=http_status.HTTP_201_CREATED,
)
async def add_gate_code(
    location_id: int,
    payload: GateCodeCreate,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> GateCodeRead:
    """Add a new active gate code. Other active codes are left as-is — a
    location can legitimately have several at once (front gate, dock, …)."""
    # 404 if the location doesn't exist.
    await _fetch_location(db, location_id)

    gate_code = GateCode(
        location_id=location_id,
        code=payload.code.strip(),
        label=payload.label.strip() if payload.label else None,
        is_active=True,
    )
    db.add(gate_code)
    await db.commit()
    await db.refresh(gate_code)
    return GateCodeRead.model_validate(gate_code)


@router.post(
    "/{location_id}/gate-codes/{code_id}/invalidate",
    response_model=GateCodeRead,
)
async def invalidate_gate_code(
    location_id: int,
    code_id: int,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> GateCodeRead:
    """Retire a gate code: mark it inactive and stamp invalidated_at. The
    row is kept as history, never deleted. Idempotent — invalidating an
    already-retired code returns it unchanged."""
    stmt = select(GateCode).where(
        GateCode.id == code_id,
        GateCode.location_id == location_id,
    )
    gate_code = (await db.execute(stmt)).scalar_one_or_none()
    if gate_code is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"gate code {code_id} not found for location {location_id}",
        )

    if gate_code.is_active:
        gate_code.is_active = False
        gate_code.invalidated_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(gate_code)
    return GateCodeRead.model_validate(gate_code)
