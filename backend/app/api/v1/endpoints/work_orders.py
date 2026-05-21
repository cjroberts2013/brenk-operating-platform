"""Work order endpoints.

Reads from the local database (populated by the sync worker). All
queries return data that's already been transformed from SC payloads
into our schema — see `app.services.sync` for the sync pipeline.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_async_db
from app.models.work_order import Client, Location, Vendor, WorkOrder, WorkOrderNote
from app.schemas.work_order import (
    WorkOrderDetail,
    WorkOrderListResponse,
    WorkOrderNoteRef,
    WorkOrderSummary,
)
from app.services.sync.work_orders import sync_all_work_orders


class WorkOrderUpdate(BaseModel):
    """PATCH body for a work order. Only Brenk-internal fields are
    writable in Phase 1 — SC-owned fields (status, dates, etc.) are
    not exposed here. Set `assigned_vendor_id` to `null` to unassign.
    """

    assigned_vendor_id: int | None = None


class WorkOrderSyncStatus(BaseModel):
    """When the work-order sync last touched the database.

    `last_synced_at` is the MAX of `work_orders.last_synced_at` — the
    UTC timestamp the sync upserter stamps onto every row it touches.
    Null only on a freshly-migrated, empty database.
    """

    last_synced_at: datetime | None
    work_order_count: int


class WorkOrderSyncSummary(BaseModel):
    """Result of POST /api/v1/work-orders/sync."""

    fetched: int
    upserted: int
    notes_synced: int
    errors: int


router = APIRouter()


_DEFAULT_PAGE_SIZE = 50
_MAX_PAGE_SIZE = 200


@router.get("/", response_model=WorkOrderListResponse)
async def list_work_orders(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    status: Annotated[
        str | None,
        Query(description="Filter by primary status (e.g., 'IN PROGRESS', 'COMPLETED')"),
    ] = None,
    client_id: Annotated[int | None, Query(description="Filter by internal client id")] = None,
    trade_id: Annotated[int | None, Query(description="Filter by internal trade id")] = None,
    assigned_vendor_id: Annotated[
        int | None,
        Query(description="Filter by assigned Brenk sub-vendor"),
    ] = None,
    updated_since: Annotated[
        datetime | None,
        Query(description="Only return WOs with sc_updated_date >= this ISO 8601 timestamp"),
    ] = None,
    q: Annotated[
        str | None,
        Query(
            description=(
                "Free-text search across WO number, SC purchase number, problem "
                "code, caller, description, store id, location name, and client "
                "name. Case-insensitive, substring match."
            ),
        ),
    ] = None,
    page: Annotated[int, Query(ge=1, description="1-indexed page number")] = 1,
    page_size: Annotated[
        int,
        Query(ge=1, le=_MAX_PAGE_SIZE, description="Records per page (max 200)"),
    ] = _DEFAULT_PAGE_SIZE,
) -> WorkOrderListResponse:
    """List work orders, filtered and paginated.

    Ordering: highest ServiceChannel work order id first. SC issues ids
    monotonically over time, so this puts the newest WOs at the top —
    matches how SC's own UI orders them, which is what Daryl is used to.
    """
    filters = []
    if status is not None:
        filters.append(WorkOrder.primary_status == status)
    if client_id is not None:
        filters.append(WorkOrder.client_id == client_id)
    if trade_id is not None:
        filters.append(WorkOrder.trade_id == trade_id)
    if assigned_vendor_id is not None:
        filters.append(WorkOrder.assigned_vendor_id == assigned_vendor_id)
    if updated_since is not None:
        filters.append(WorkOrder.sc_updated_date >= updated_since)

    # Free-text search. We OR across columns the operator is likely to
    # type — WO number, SC purchase number, problem code, caller free
    # text, description, and the joined Location/Client name fields.
    # Outer joins so a WO with no client/location still matches on its
    # own columns. Substring match via ILIKE — postgres handles case
    # folding natively, no need to LOWER() both sides.
    needs_search_joins = False
    if q is not None and q.strip():
        needle = f"%{q.strip()}%"
        needs_search_joins = True
        filters.append(
            or_(
                WorkOrder.sc_number.ilike(needle),
                WorkOrder.sc_purchase_number.ilike(needle),
                WorkOrder.problem_code.ilike(needle),
                WorkOrder.caller.ilike(needle),
                WorkOrder.description.ilike(needle),
                Location.store_id.ilike(needle),
                Location.name.ilike(needle),
                Client.name.ilike(needle),
                Client.short_name.ilike(needle),
            )
        )

    def _apply_filters(stmt):
        if needs_search_joins:
            stmt = stmt.outerjoin(Location, WorkOrder.location_id == Location.id)
            stmt = stmt.outerjoin(Client, WorkOrder.client_id == Client.id)
        if filters:
            stmt = stmt.where(*filters)
        return stmt

    count_stmt = _apply_filters(select(func.count(WorkOrder.id)).select_from(WorkOrder))
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(WorkOrder)
        .options(
            selectinload(WorkOrder.client),
            selectinload(WorkOrder.location),
            selectinload(WorkOrder.trade),
        )
        .order_by(WorkOrder.sc_work_order_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    stmt = _apply_filters(stmt)
    rows = (await db.execute(stmt)).scalars().all()

    return WorkOrderListResponse(
        items=[WorkOrderSummary.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/sync-status", response_model=WorkOrderSyncStatus)
async def get_work_order_sync_status(
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> WorkOrderSyncStatus:
    """Return when the WO sync last touched the local DB.

    Cheap query (single MAX + COUNT), called by the WO list page header
    to render "Last synced 12 minutes ago · 341 work orders".

    NOTE: registered above the `/{work_order_id}` path-param route so
    `/sync-status` doesn't get swallowed as a numeric id parse error.
    """
    last, count = (
        await db.execute(select(func.max(WorkOrder.last_synced_at), func.count(WorkOrder.id)))
    ).one()
    return WorkOrderSyncStatus(last_synced_at=last, work_order_count=count)


@router.post("/sync", response_model=WorkOrderSyncSummary)
async def trigger_work_order_sync() -> WorkOrderSyncSummary:
    """Trigger an immediate sync from SC. Runs inline (not via the
    Procrastinate queue) so the operator sees the result in their
    response. The scheduled hourly sync still runs in the background.

    Idempotent. Calling repeatedly is fine — the upserter is keyed on
    `sc_work_order_id` and counts each WO once per call.
    """
    summary = await sync_all_work_orders()
    return WorkOrderSyncSummary(
        fetched=summary["fetched"],
        upserted=summary["upserted"],
        notes_synced=summary["notes_synced"],
        errors=len(summary["errors"]),
    )


async def _fetch_work_order(
    db: AsyncSession,
    work_order_id: int,
    *,
    populate_existing: bool = False,
) -> WorkOrder:
    """Load a WO with all relationships eager-loaded, or raise 404.

    Centralized so the GET and PATCH endpoints can't drift apart on which
    relationships they eager-load — both call this helper.

    `populate_existing=True` bypasses the session's identity-map cache —
    use it after a PATCH so the response reflects the freshly-updated
    relationships (otherwise SQLAlchemy returns the in-memory copy that
    still has the pre-update relationship snapshot).
    """
    stmt = (
        select(WorkOrder)
        .options(
            selectinload(WorkOrder.client),
            selectinload(WorkOrder.location),
            selectinload(WorkOrder.trade),
            selectinload(WorkOrder.assigned_vendor),
        )
        .where(WorkOrder.id == work_order_id)
    )
    if populate_existing:
        stmt = stmt.execution_options(populate_existing=True)
    wo = (await db.execute(stmt)).scalar_one_or_none()
    if wo is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"work order {work_order_id} not found",
        )
    return wo


@router.get("/{work_order_id}", response_model=WorkOrderDetail)
async def get_work_order(
    work_order_id: int,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> WorkOrderDetail:
    """Get a single work order by its internal database id.

    Returns 404 if no such work order exists.
    """
    wo = await _fetch_work_order(db, work_order_id)
    return WorkOrderDetail.model_validate(wo)


@router.patch("/{work_order_id}", response_model=WorkOrderDetail)
async def update_work_order(
    work_order_id: int,
    payload: WorkOrderUpdate,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> WorkOrderDetail:
    """Update Brenk-internal fields on a work order.

    Phase 1: only `assigned_vendor_id` is writable. Pass `null` to
    unassign. Anything SC owns (status, dates, notes_count, etc.) is
    not touched — those flow in via the sync worker.
    """
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        # No-op PATCH: surface the current state, don't error.
        return await get_work_order(work_order_id, db)

    wo = await _fetch_work_order(db, work_order_id)

    if "assigned_vendor_id" in update_data:
        new_vendor_id = update_data["assigned_vendor_id"]
        if new_vendor_id is not None:
            exists = (
                await db.execute(select(Vendor.id).where(Vendor.id == new_vendor_id))
            ).scalar_one_or_none()
            if exists is None:
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail=f"vendor {new_vendor_id} not found",
                )
        wo.assigned_vendor_id = new_vendor_id

    await db.commit()
    # populate_existing rebuilds the in-memory WO from the new SELECT
    # results — picks up the server-side onupdate (`updated_at`) plus
    # any relationship that changed. Without it, the session's identity
    # map returns the pre-PATCH copy of the WO.
    fresh = await _fetch_work_order(db, work_order_id, populate_existing=True)
    return WorkOrderDetail.model_validate(fresh)


@router.get("/{work_order_id}/notes", response_model=list[WorkOrderNoteRef])
async def list_work_order_notes(
    work_order_id: int,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> list[WorkOrderNoteRef]:
    """List notes for a single work order, oldest first.

    Returns 404 if the work order itself doesn't exist. Returns an empty
    list (not 404) if the WO exists but has no notes.
    """
    wo_exists = (
        await db.execute(select(WorkOrder.id).where(WorkOrder.id == work_order_id))
    ).scalar_one_or_none()
    if wo_exists is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"work order {work_order_id} not found",
        )

    stmt = (
        select(WorkOrderNote)
        .where(WorkOrderNote.work_order_id == work_order_id)
        .order_by(WorkOrderNote.note_number.asc().nullslast(), WorkOrderNote.id.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [WorkOrderNoteRef.model_validate(row) for row in rows]
