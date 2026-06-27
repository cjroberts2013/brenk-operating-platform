"""Vendor workload counts — one grouped query, shared across endpoints.

`active_work_order_counts` is the single source of truth for "how many open
work orders is this vendor carrying right now." The vendors list, the vendor
detail, and the vendor-suggestion endpoint all read from it so the number
they show can never drift.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.work_order import WorkOrder, WoVendorAssignment

# A work order in one of these primary statuses is finished and no longer
# counts against a vendor's current load.
TERMINAL_STATUSES = ("COMPLETED", "CANCELLED")


async def active_work_order_counts(db: AsyncSession, vendor_ids: list[int]) -> dict[int, int]:
    """Return {vendor_id: count of non-terminal work orders assigned}.

    Counts via the multi-vendor junction, so a vendor's load includes WOs where
    they're a secondary assignment — not only where they're the primary. One
    grouped query for the whole batch (no N+1).
    """
    if not vendor_ids:
        return {}
    stmt = (
        select(
            WoVendorAssignment.vendor_id,
            func.count(func.distinct(WoVendorAssignment.work_order_id)),
        )
        .join(WorkOrder, WorkOrder.id == WoVendorAssignment.work_order_id)
        .where(
            WoVendorAssignment.vendor_id.in_(vendor_ids),
            WorkOrder.primary_status.notin_(TERMINAL_STATUSES),
        )
        .group_by(WoVendorAssignment.vendor_id)
    )
    rows = (await db.execute(stmt)).all()
    return {row[0]: row[1] for row in rows if row[0] is not None}
