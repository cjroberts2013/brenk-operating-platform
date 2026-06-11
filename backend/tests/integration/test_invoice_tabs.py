"""Integration tests for the invoice-queue tab classification.

Creates synthetic work orders (ids >= 999001000) with various SC invoice
states and asserts each lands in exactly the right `invoice_tab`. Cleans
up on teardown.
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
from app.models.work_order import WorkOrder

BASE = 999001000
# name -> (sc_work_order_id, kwargs) describing the WO's billing state
CASES = {
    "ready": dict(primary_status="COMPLETED", extended_status="CONFIRMED"),
    "marked": dict(
        primary_status="COMPLETED",
        extended_status="CONFIRMED",
        brenk_markup_percent=Decimal("50"),
    ),
    "sent": dict(
        primary_status="COMPLETED", extended_status="CONFIRMED", sc_invoice_status="Open"
    ),
    "paid": dict(
        primary_status="COMPLETED", extended_status="CONFIRMED", sc_invoice_status="Paid"
    ),
    "rejected": dict(
        primary_status="COMPLETED",
        extended_status="CONFIRMED",
        sc_invoice_status="Rejected",
    ),
    "voided": dict(
        primary_status="COMPLETED", extended_status="CONFIRMED", sc_invoice_status="Void"
    ),
    "legacy": dict(primary_status="INVOICED"),  # invoiced before webhooks
}


@pytest.fixture
async def env(
    auth_headers: dict[str, str],
) -> AsyncGenerator[tuple[httpx.AsyncClient, dict[str, str]]]:
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL_ASYNC, poolclass=NullPool)
    factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )
    numbers: dict[str, str] = {}
    async with factory() as s:
        for i, (name, kwargs) in enumerate(CASES.items()):
            woid = BASE + i
            num = f"ITAB{woid}"
            numbers[name] = num
            s.add(WorkOrder(sc_work_order_id=woid, sc_number=num, **kwargs))
        await s.commit()

    async def _override() -> AsyncGenerator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_async_db] = _override
    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", headers=auth_headers
        ) as ac:
            yield ac, numbers
    finally:
        app.dependency_overrides.pop(get_async_db, None)
        async with factory() as s:
            await s.execute(delete(WorkOrder).where(WorkOrder.sc_work_order_id >= BASE))
            await s.commit()
        await engine.dispose()


async def _tab(client: httpx.AsyncClient, tab: str) -> set[str]:
    r = await client.get(
        "/api/v1/work-orders/", params={"invoice_tab": tab, "page_size": 200}
    )
    assert r.status_code == 200
    return {it["sc_number"] for it in r.json()["items"]}


async def test_each_wo_lands_in_exactly_one_tab(
    env: tuple[httpx.AsyncClient, dict[str, str]],
) -> None:
    client, num = env
    tabs = {t: await _tab(client, t) for t in
            ("ready_to_markup", "marked_up", "sent", "rejected", "paid")}

    # Expected tab per case.
    expected = {
        "ready": "ready_to_markup",
        "marked": "marked_up",
        "sent": "sent",
        "paid": "paid",
        "rejected": "rejected",
        "voided": "ready_to_markup",  # void -> back to needs-invoicing
        "legacy": "sent",             # primary_status=INVOICED fallback
    }
    for case, tab in expected.items():
        n = num[case]
        assert n in tabs[tab], f"{case} ({n}) should be in {tab}"
        # And in no other tab.
        for other in tabs:
            if other != tab:
                assert n not in tabs[other], f"{case} ({n}) leaked into {other}"


async def test_sent_summary_exposes_invoice_fields(
    env: tuple[httpx.AsyncClient, dict[str, str]],
) -> None:
    client, num = env
    r = await client.get(
        "/api/v1/work-orders/", params={"invoice_tab": "sent", "page_size": 200}
    )
    row = next(it for it in r.json()["items"] if it["sc_number"] == num["sent"])
    assert row["sc_invoice_status"] == "Open"
    assert "sc_invoice_number" in row and "sc_invoice_total" in row
