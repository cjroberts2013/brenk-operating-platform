"""End-to-end smoke test: pull WOs from ServiceChannel Sandbox2 and upsert into Supabase.

Run from the backend directory with the venv activated:

    python scripts/test_sync.py

This hits the real SC sandbox API and the real (dev) Supabase database.
"""

import asyncio

from sqlalchemy import func, select

from app.db.session import AsyncSessionLocal
from app.models.work_order import (
    Client,
    Location,
    Trade,
    WorkOrder,
    WorkOrderStatusHistory,
)
from app.services.sync.work_orders import sync_recent_work_orders


async def _count(model) -> int:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(func.count()).select_from(model))
        return result.scalar_one()


async def main() -> None:
    print("=" * 60)
    print("DB state BEFORE sync")
    print("=" * 60)
    for model in (Client, Location, Trade, WorkOrder, WorkOrderStatusHistory):
        print(f"  {model.__tablename__:<25} {await _count(model)}")

    print()
    print("=" * 60)
    print("Running sync_recent_work_orders(lookback_hours=720)")
    print("=" * 60)
    summary = await sync_recent_work_orders(lookback_hours=720)
    print(f"  fetched:  {summary['fetched']}")
    print(f"  upserted: {summary['upserted']}")
    print(f"  errors:   {len(summary['errors'])}")
    for err in summary["errors"][:5]:
        print(f"    - sc_id={err['sc_work_order_id']}: {err['error']}")

    print()
    print("=" * 60)
    print("DB state AFTER sync")
    print("=" * 60)
    for model in (Client, Location, Trade, WorkOrder, WorkOrderStatusHistory):
        print(f"  {model.__tablename__:<25} {await _count(model)}")

    print()
    print("=" * 60)
    print("Sample work orders (first 5)")
    print("=" * 60)
    async with AsyncSessionLocal() as session:
        stmt = select(WorkOrder).limit(5)
        for wo in (await session.execute(stmt)).scalars():
            print(
                f"  #{wo.sc_number}  {wo.primary_status}/{wo.extended_status}  "
                f"trade_id={wo.trade_id}  loc_id={wo.location_id}"
            )


if __name__ == "__main__":
    asyncio.run(main())
