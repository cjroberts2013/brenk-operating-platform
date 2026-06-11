"""Actual SC invoice records (synced from invoice webhooks).

Invoice-centric list for the Invoices page: one row per real invoice in
the `invoices` table, joined to its work order for context + navigation.
Distinct from the work-order billing worklist on `/work-orders`.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_db
from app.models.invoice import Invoice
from app.models.work_order import Location, WorkOrder
from app.schemas.work_order import InvoiceListItem, InvoiceListResponse

router = APIRouter()

_DEFAULT_PAGE_SIZE = 50
_MAX_PAGE_SIZE = 200


@router.get("/", response_model=InvoiceListResponse)
async def list_invoices(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    status: Annotated[
        str | None,
        Query(description="Filter by exact SC invoice status (Open, Approved, Paid, Rejected, Void, ...)."),
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=_MAX_PAGE_SIZE)] = _DEFAULT_PAGE_SIZE,
) -> InvoiceListResponse:
    """List actual SC invoices, newest first, with their linked WO."""
    filters = []
    if status:
        filters.append(Invoice.status == status)

    count_stmt = select(func.count(Invoice.id))
    if filters:
        count_stmt = count_stmt.where(*filters)
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(
            Invoice,
            WorkOrder.id,
            WorkOrder.sc_number,
            Location.name,
            Location.store_id,
        )
        .outerjoin(WorkOrder, WorkOrder.sc_work_order_id == Invoice.wo_tracking_number)
        .outerjoin(Location, Location.id == WorkOrder.location_id)
    )
    if filters:
        stmt = stmt.where(*filters)
    stmt = (
        stmt.order_by(Invoice.sc_updated_date.desc().nullslast(), Invoice.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    rows = (await db.execute(stmt)).all()
    items: list[InvoiceListItem] = []
    for inv, wo_id, wo_number, loc_name, loc_store in rows:
        item = InvoiceListItem.model_validate(inv)
        item.work_order_id = wo_id
        item.wo_number = wo_number
        item.location_name = loc_name
        item.location_store_id = loc_store
        items.append(item)

    return InvoiceListResponse(
        items=items, total=total, page=page, page_size=page_size
    )
