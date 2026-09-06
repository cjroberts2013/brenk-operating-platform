"""Integration test for the WO-sync reconcile pass.

SC drops a work order from its /v3/workorders list feed once it COMPLETES,
so the list sweep never sees the completion and our copy stays frozen at
IN PROGRESS. The reconcile pass re-fetches such WOs individually. Seeds a
stale IN PROGRESS WO in the dev DB, runs sync with a mock SC client whose
list feed is empty but whose single-WO GET returns COMPLETED, and asserts
the local row flips.
"""

from collections.abc import AsyncGenerator, AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.exceptions import ServiceChannelNotFoundError
from app.models.work_order import Client, Location, WorkOrder
from app.services.sync.work_orders import sync_all_work_orders

SC_BASE = 999005000


def _wo_payload(sc_id: int, primary: str, extended: str | None) -> dict[str, Any]:
    """Minimal but valid single-WO SC payload the upserter can process."""
    return {
        "Id": sc_id,
        "Number": str(sc_id),
        "Status": {"Primary": primary, "Extended": extended},
        "Subscriber": {"Id": SC_BASE, "Name": "SC Test Client"},
        "Location": {"Id": SC_BASE, "StoreId": "0751", "Name": "STASSNEY"},
        "Currency": {"AlphabeticalCode": "USD"},
        "Notes": {"Count": {"Total": 0}},
        "Attachments": {"Count": {"Total": 0}},
    }


class _MockSC:
    """Empty list feed (WO dropped), configurable single-WO GET."""

    def __init__(self, get_result: dict | Exception):
        self._get_result = get_result

    async def iter_work_orders(self, **_kw) -> AsyncIterator[dict]:
        return
        yield  # make this an async generator

    async def get_work_order(self, sc_id: int) -> dict:
        if isinstance(self._get_result, Exception):
            raise self._get_result
        return self._get_result


@pytest.fixture
async def factory() -> AsyncGenerator[async_sessionmaker]:
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL_ASYNC, poolclass=NullPool)
    fac = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def _cleanup() -> None:
        async with fac() as s:
            await s.execute(delete(WorkOrder).where(WorkOrder.sc_work_order_id >= SC_BASE))
            await s.execute(delete(Location).where(Location.sc_location_id == SC_BASE))
            await s.execute(delete(Client).where(Client.sc_subscriber_id == SC_BASE))
            await s.commit()

    await _cleanup()
    try:
        yield fac
    finally:
        await _cleanup()
        await engine.dispose()


async def _seed_stale_in_progress(fac: async_sessionmaker, sc_id: int) -> None:
    async with fac() as s:
        client = Client(sc_subscriber_id=SC_BASE, name="SC Test Client")
        s.add(client)
        await s.flush()
        loc = Location(
            sc_location_id=SC_BASE, client_id=client.id, store_id="0751", name="STASSNEY"
        )
        s.add(loc)
        await s.flush()
        s.add(
            WorkOrder(
                sc_work_order_id=sc_id,
                sc_number=str(sc_id),
                primary_status="IN PROGRESS",
                extended_status="DISPATCH CONFIRMED",
                location_id=loc.id,
                client_id=client.id,
                last_synced_at=datetime.now(UTC) - timedelta(days=90),  # stale
            )
        )
        await s.commit()


async def test_reconcile_flips_dropped_wo_to_completed(factory) -> None:
    sc_id = SC_BASE + 1
    await _seed_stale_in_progress(factory, sc_id)

    mock = _MockSC(_wo_payload(sc_id, "COMPLETED", "CONFIRMED"))
    summary = await sync_all_work_orders(sc_client=mock)

    assert summary["reconciled"] == 1
    async with factory() as s:
        wo = (
            await s.execute(select(WorkOrder).where(WorkOrder.sc_work_order_id == sc_id))
        ).scalar_one()
        assert wo.primary_status == "COMPLETED"
        assert wo.extended_status == "CONFIRMED"


async def test_reconcile_marks_wo_deleted_from_sc(factory) -> None:
    sc_id = SC_BASE + 2
    await _seed_stale_in_progress(factory, sc_id)

    mock = _MockSC(ServiceChannelNotFoundError("Not found"))
    summary = await sync_all_work_orders(sc_client=mock)

    # A 404 means SC deleted the WO: not counted as reconciled, not an
    # error — marked deleted so deadline tracking drops it.
    assert summary["reconciled"] == 0
    assert summary["marked_deleted"] == 1
    assert len(summary["errors"]) == 0
    async with factory() as s:
        wo = (
            await s.execute(select(WorkOrder).where(WorkOrder.sc_work_order_id == sc_id))
        ).scalar_one()
        assert wo.primary_status == "IN PROGRESS"  # status left as-is
        assert wo.brenk_sc_deleted_at is not None  # but marked deleted


async def test_reconcile_clears_deleted_marker_when_wo_reappears(factory) -> None:
    sc_id = SC_BASE + 3
    await _seed_stale_in_progress(factory, sc_id)
    # First run: SC 404s → marked deleted.
    await sync_all_work_orders(sc_client=_MockSC(ServiceChannelNotFoundError("gone")))
    # Second run: the WO is back and COMPLETED → marker cleared on upsert.
    summary = await sync_all_work_orders(
        sc_client=_MockSC(_wo_payload(sc_id, "COMPLETED", "CONFIRMED"))
    )
    assert summary["reconciled"] == 1
    async with factory() as s:
        wo = (
            await s.execute(select(WorkOrder).where(WorkOrder.sc_work_order_id == sc_id))
        ).scalar_one()
        assert wo.primary_status == "COMPLETED"
        assert wo.brenk_sc_deleted_at is None  # self-healed
