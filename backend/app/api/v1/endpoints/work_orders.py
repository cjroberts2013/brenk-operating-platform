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
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_async_db
from app.models.work_order import Vendor, WorkOrder, WorkOrderNote
from app.schemas.work_order import (
    WorkOrderDetail,
    WorkOrderListResponse,
    WorkOrderNoteRef,
    WorkOrderSummary,
)


class WorkOrderUpdate(BaseModel):
    """PATCH body for a work order. Only Brenk-internal fields are
    writable in Phase 1 — SC-owned fields (status, dates, etc.) are
    not exposed here. Set `assigned_vendor_id` to `null` to unassign.
    """

    assigned_vendor_id: int | None = None

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
    updated_since: Annotated[
        datetime | None,
        Query(description="Only return WOs with sc_updated_date >= this ISO 8601 timestamp"),
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
    if updated_since is not None:
        filters.append(WorkOrder.sc_updated_date >= updated_since)

    count_stmt = select(func.count()).select_from(WorkOrder)
    if filters:
        count_stmt = count_stmt.where(*filters)
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
    if filters:
        stmt = stmt.where(*filters)
    rows = (await db.execute(stmt)).scalars().all()

    return WorkOrderListResponse(
        items=[WorkOrderSummary.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
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
                await db.execute(
                    select(Vendor.id).where(Vendor.id == new_vendor_id)
                )
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
