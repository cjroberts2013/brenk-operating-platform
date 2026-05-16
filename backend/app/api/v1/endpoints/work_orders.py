"""Work order endpoints.

These are stubs for Phase 1 / Week 3. The actual implementations will read
from the local database (populated by the sync worker), not from SC directly.
"""

from fastapi import APIRouter, HTTPException, status

router = APIRouter()


@router.get("/")
async def list_work_orders() -> dict:
    """List work orders. To be implemented in Week 3."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="List work orders not yet implemented",
    )


@router.get("/{work_order_id}")
async def get_work_order(work_order_id: int) -> dict:
    """Get a single work order by ID. To be implemented in Week 3."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Get work order not yet implemented",
    )
