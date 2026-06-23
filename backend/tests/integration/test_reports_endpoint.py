"""Integration test for GET /api/v1/reports/summary — the revenue/volume by
category + coverage additions. Seeds one categorized + invoiced + priced WO
in a low-traffic category so its billed total is isolated.
"""

from collections.abc import AsyncGenerator
from decimal import Decimal

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.db.session import get_async_db
from app.main import app
from app.models.invoice import Invoice
from app.models.work_order import Client, WorkOrder

SC_BASE = 999005000
# A real taxonomy category with no real invoices in dev, so our seeded
# invoice total is the only contribution to its billed figure.
TEST_CATEGORY = "Pest Control"


@pytest.fixture
async def client() -> AsyncGenerator[httpx.AsyncClient]:
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL_ASYNC, poolclass=NullPool)
    factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )

    async def _override() -> AsyncGenerator[AsyncSession]:
        async with factory() as session:
            yield session

    async def _cleanup() -> None:
        async with factory() as s:
            await s.execute(delete(Invoice).where(Invoice.wo_tracking_number == SC_BASE))
            await s.execute(delete(WorkOrder).where(WorkOrder.sc_work_order_id == SC_BASE))
            await s.execute(delete(Client).where(Client.sc_subscriber_id == SC_BASE))
            await s.commit()

    async def _seed() -> None:
        async with factory() as s:
            c = Client(sc_subscriber_id=SC_BASE, name="Reports Test Client")
            s.add(c)
            await s.flush()
            s.add(
                WorkOrder(
                    sc_work_order_id=SC_BASE,
                    sc_number=str(SC_BASE),
                    primary_status="INVOICED",
                    brenk_category=TEST_CATEGORY,
                    brenk_labor_cost=Decimal("100.00"),
                    brenk_markup_percent=Decimal("80.00"),
                    client_id=c.id,
                )
            )
            s.add(
                Invoice(
                    sc_env="sandbox",
                    invoice_number="ITESTREPORT",
                    source="backfill",
                    wo_tracking_number=SC_BASE,
                    status="Paid",
                    invoice_total=Decimal("200.00"),
                )
            )
            await s.commit()

    app.dependency_overrides[get_async_db] = _override
    await _cleanup()
    await _seed()
    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_async_db, None)
        await _cleanup()
        await engine.dispose()


async def test_reports_category_overview_and_coverage(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    resp = await client.get("/api/v1/reports/summary", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Coverage reflects our priced + invoiced WO.
    assert body["coverage"] is not None
    assert body["coverage"]["invoiced_jobs"] >= 1
    assert body["coverage"]["priced_jobs"] >= 1

    # Our category's billed revenue = the seeded invoice total.
    overview = {c["category"]: c for c in body["category_overview"]}
    assert TEST_CATEGORY in overview
    row = overview[TEST_CATEGORY]
    assert row["jobs"] >= 1
    assert row["invoiced_jobs"] >= 1
    assert row["billed"] == "200.00"
    assert row["paid"] == "200.00"

    # And it shows up in the markup (profit) breakdown too.
    cats = {c["category"] for c in body["markup_by_category"]}
    assert TEST_CATEGORY in cats
