"""Integration tests for invoice preview + submit endpoints.

Hits the real dev DB with synthetic WOs (ids >= 999001000, cleaned on
teardown). The SC POST is monkeypatched — tests never touch the real SC
API (per repo conventions).
"""

from collections.abc import AsyncGenerator
from decimal import Decimal

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.exceptions import ServiceChannelError
from app.db.session import get_async_db
from app.main import app
from app.models.work_order import WorkOrder
from app.services.servicechannel.client import ServiceChannelClient

TEST_WO_ID = 999001000


@pytest.fixture
async def harness(
    auth_headers: dict[str, str],
) -> AsyncGenerator[tuple[httpx.AsyncClient, async_sessionmaker]]:
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL_ASYNC, poolclass=NullPool)
    factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )

    async def _override() -> AsyncGenerator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_async_db] = _override
    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", headers=auth_headers
        ) as ac:
            yield ac, factory
    finally:
        app.dependency_overrides.pop(get_async_db, None)
        async with factory() as session:
            await session.execute(
                delete(WorkOrder).where(WorkOrder.sc_work_order_id >= TEST_WO_ID)
            )
            await session.commit()
        await engine.dispose()


async def _make_wo(factory: async_sessionmaker, **overrides) -> int:
    defaults = dict(
        sc_work_order_id=TEST_WO_ID,
        sc_number="ITESTSUBMIT1",
        primary_status="COMPLETED",
        extended_status="CONFIRMED",
        brenk_labor_cost=Decimal("100.00"),
        brenk_material_cost=Decimal("50.00"),
        brenk_markup_percent=Decimal("65.00"),
        nte=Decimal("500.00"),
        resolution="Replaced the gate loop detector.",
    )
    defaults.update(overrides)
    async with factory() as session:
        wo = WorkOrder(**defaults)
        session.add(wo)
        await session.commit()
        return wo.id


async def test_preview_eligible(harness) -> None:
    ac, factory = harness
    wo_id = await _make_wo(factory)
    resp = await ac.get(f"/api/v1/work-orders/{wo_id}/invoice-preview")
    assert resp.status_code == 200
    body = resp.json()
    assert body["eligible"] is True
    assert body["problems"] == []
    assert body["invoice_number"] == "BRENKITESTSUBMIT1"
    assert body["subtotal"] == "247.50"
    assert body["tax_amount"] == "20.42"  # 8.25% TX sales tax
    assert body["invoice_total"] == "267.92"
    assert body["resolution_text"] == "Replaced the gate loop detector."


async def test_preview_reports_problems(harness) -> None:
    ac, factory = harness
    wo_id = await _make_wo(factory, brenk_markup_percent=None, resolution=None)
    body = (await ac.get(f"/api/v1/work-orders/{wo_id}/invoice-preview")).json()
    assert body["eligible"] is False
    assert any("markup" in p.lower() for p in body["problems"])
    assert any("resolution" in p.lower() for p in body["problems"])


async def test_submit_success_records_invoice(
    harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    ac, factory = harness
    wo_id = await _make_wo(factory)

    sent_payloads: list[dict] = []

    async def fake_create_invoice(self, payload):
        sent_payloads.append(payload)
        return {"Id": 999000555}

    monkeypatch.setattr(ServiceChannelClient, "create_invoice", fake_create_invoice)

    resp = await ac.post(
        f"/api/v1/work-orders/{wo_id}/submit-invoice", json={"invoice_text": None}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["sc_invoice_id"] == 999000555
    assert body["sc_invoice_number"] == "BRENKITESTSUBMIT1"
    assert body["sc_invoice_status"] == "Open"
    assert body["sc_invoice_total"] == "267.92"  # incl. 8.25% tax
    assert body["sc_invoice_submitted_at"] is not None

    # The payload SC received carried marked-up amounts, not vendor costs.
    assert len(sent_payloads) == 1
    sent = sent_payloads[0]
    assert sent["InvoiceTotal"] == 267.92
    assert sent["InvoiceTax"] == 20.42
    assert sent["InvoiceAmountsDetails"]["LaborAmount"] == 165.0
    # Raw vendor costs (100/50) and markup % (65) never sent; no brenk_*
    # field names leak into the payload.
    assert 100.0 not in sent["InvoiceAmountsDetails"].values()
    assert 50.0 not in sent["InvoiceAmountsDetails"].values()
    assert "brenk_" not in str(sent).lower()
    assert "markup" not in str(sent).lower()

    # Persisted on the WO too.
    async with factory() as session:
        wo = (
            await session.execute(select(WorkOrder).where(WorkOrder.id == wo_id))
        ).scalar_one()
        assert wo.sc_invoice_id == 999000555
        assert wo.sc_invoice_status == "Open"


async def test_submit_validation_failure_is_400(harness) -> None:
    ac, factory = harness
    wo_id = await _make_wo(factory, brenk_markup_percent=None)
    resp = await ac.post(f"/api/v1/work-orders/{wo_id}/submit-invoice", json={})
    assert resp.status_code == 400
    assert "markup" in resp.json()["detail"].lower()


async def test_submit_sc_rejection_is_400_and_recorded(
    harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    ac, factory = harness
    wo_id = await _make_wo(factory)

    async def fake_reject(self, payload):
        raise ServiceChannelError(
            'SC API error: 400 {"ErrorCodes":[1180],"ErrorCode":1180,'
            '"ErrorMessage":"Invoice Number is not correct"}'
        )

    monkeypatch.setattr(ServiceChannelClient, "create_invoice", fake_reject)

    resp = await ac.post(f"/api/v1/work-orders/{wo_id}/submit-invoice", json={})
    assert resp.status_code == 400
    assert "Invoice Number is not correct" in resp.json()["detail"]

    # Rejection reason persisted for the "last submit failed" surface.
    async with factory() as session:
        wo = (
            await session.execute(select(WorkOrder).where(WorkOrder.id == wo_id))
        ).scalar_one()
        assert wo.sc_invoice_last_error is not None
        assert "Invoice Number" in wo.sc_invoice_last_error
        assert wo.sc_invoice_id is None  # nothing recorded as created
