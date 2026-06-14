"""Actual SC invoice records (synced from invoice webhooks).

Invoice-centric list for the Invoices page: one row per real invoice in
the `invoices` table, joined to its work order for context + navigation.
Distinct from the work-order billing worklist on `/work-orders`.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_db
from app.models.invoice import Invoice
from app.models.work_order import Location, WorkOrder
from app.schemas.work_order import InvoiceListItem, InvoiceListResponse
from app.services.money import ACTIVE_INVOICE_STATUSES

router = APIRouter()

_DEFAULT_PAGE_SIZE = 50
_MAX_PAGE_SIZE = 200

# Named status buckets for the Invoices page tabs. "awaiting" reuses the
# same active set the dashboard + WO queue use, so the three surfaces
# always agree on what counts as in-flight.
_STATUS_GROUPS: dict[str, list[str]] = {
    "awaiting": sorted(ACTIVE_INVOICE_STATUSES),
    "paid": ["Paid"],
    "rejected": ["Rejected"],
}


@router.get("/", response_model=InvoiceListResponse)
async def list_invoices(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    status: Annotated[
        str | None,
        Query(description="Filter by exact SC invoice status (Open, Approved, Paid, Rejected, Void, ...)."),
    ] = None,
    status_group: Annotated[
        str | None,
        Query(description="Named bucket: awaiting | paid | rejected. Omit/'all' for everything."),
    ] = None,
    q: Annotated[
        str | None,
        Query(description="Free-text search across invoice #, WO #, location, and trade."),
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=_MAX_PAGE_SIZE)] = _DEFAULT_PAGE_SIZE,
) -> InvoiceListResponse:
    """List actual SC invoices, newest first, with their linked WO."""
    filters = []
    if status:
        filters.append(Invoice.status == status)
    if status_group and status_group in _STATUS_GROUPS:
        filters.append(Invoice.status.in_(_STATUS_GROUPS[status_group]))
    if q and q.strip():
        like = f"%{q.strip()}%"
        filters.append(
            or_(
                Invoice.invoice_number.ilike(like),
                cast(Invoice.wo_tracking_number, String).ilike(like),
                Location.name.ilike(like),
                Location.store_id.ilike(like),
                Invoice.trade.ilike(like),
            )
        )

    # The join is 1:1 (each invoice links to at most one WO/Location), so
    # count(Invoice.id) stays correct even with the joins present — and we
    # need them because `q` can match on the joined location columns.
    def joined(stmt):
        return stmt.outerjoin(
            WorkOrder, WorkOrder.sc_work_order_id == Invoice.wo_tracking_number
        ).outerjoin(Location, Location.id == WorkOrder.location_id)

    count_stmt = joined(select(func.count(Invoice.id)))
    if filters:
        count_stmt = count_stmt.where(*filters)
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = joined(
        select(
            Invoice,
            WorkOrder.id,
            WorkOrder.sc_number,
            Location.name,
            Location.store_id,
        )
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
