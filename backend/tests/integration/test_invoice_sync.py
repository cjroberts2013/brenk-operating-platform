"""Integration tests for app.services.invoice_sync.

Runs against the real dev DB. All test rows use ids >= 999000000 and are
deleted on teardown, so the DB is left as found.
"""

import hashlib
import json
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.models.invoice import (
    Invoice,
    InvoiceLabor,
    InvoiceMaterial,
    InvoiceStatusHistory,
    WebhookEvent,
)
from app.models.work_order import WorkOrder
from app.services.invoice_sync import process_event

ENV = get_settings().SC_ENVIRONMENT
TEST_FLOOR = 999000000
TEST_WO = 999000900


def _obj(inv_id: int, number: str, **extra: Any) -> dict[str, Any]:
    obj: dict[str, Any] = {
        "Id": inv_id,
        "Number": number,
        "Status": extra.pop("Status", "Open"),
        "UpdatedDate": extra.pop("UpdatedDate", "2026-06-10T10:00:00Z"),
    }
    obj.update(extra)
    return obj


def _event(event_type: str, obj: dict[str, Any]) -> dict[str, Any]:
    return {"EventType": event_type, "Object": obj}


@pytest.fixture
async def db() -> AsyncGenerator[AsyncSession]:
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL_ASYNC, poolclass=NullPool)
    factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )
    async with factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await session.execute(
                delete(InvoiceLabor).where(InvoiceLabor.sc_invoice_id >= TEST_FLOOR)
            )
            await session.execute(
                delete(InvoiceMaterial).where(InvoiceMaterial.sc_invoice_id >= TEST_FLOOR)
            )
            await session.execute(
                delete(InvoiceStatusHistory).where(
                    InvoiceStatusHistory.sc_invoice_id >= TEST_FLOOR
                )
            )
            await session.execute(delete(Invoice).where(Invoice.sc_invoice_id >= TEST_FLOOR))
            await session.execute(
                delete(WebhookEvent).where(WebhookEvent.object_id >= TEST_FLOOR)
            )
            await session.execute(
                delete(WorkOrder).where(WorkOrder.sc_work_order_id >= TEST_WO)
            )
            await session.commit()
    await engine.dispose()


async def _store(session: AsyncSession, body: Any, *, object_id: int) -> int:
    raw = body if isinstance(body, bytes) else json.dumps(body).encode()
    event_type = body.get("EventType") if isinstance(body, dict) else None
    ev = WebhookEvent(
        sc_env=ENV,
        raw_body=raw,
        signature_valid=True,
        status="pending",
        event_type=event_type,
        object_id=object_id,
        dedupe_key=hashlib.sha256(raw).hexdigest(),
    )
    session.add(ev)
    await session.commit()
    return ev.id


async def _get_invoice(session: AsyncSession, sc_invoice_id: int) -> Invoice | None:
    return (
        await session.execute(
            select(Invoice).where(Invoice.sc_invoice_id == sc_invoice_id)
        )
    ).scalar_one_or_none()


async def test_invoice_created_materializes(db: AsyncSession) -> None:
    body = _event(
        "InvoiceCreated",
        _obj(
            999000010,
            "ITESTA",
            InvoiceTotal=100,
            Labors=[{"SkillLevel": 2, "LaborType": 1, "HourlyRate": 60, "Hours": 1, "Amount": 60}],
            Materials=[{"Description": "part", "UnitPrice": 40, "Quantity": 1, "Amount": 40}],
        ),
    )
    eid = await _store(db, body, object_id=999000010)
    assert await process_event(db, eid, sc_env=ENV) == "processed"

    inv = await _get_invoice(db, 999000010)
    assert inv is not None
    assert inv.status == "Open"
    assert inv.source == "webhook"
    assert inv.invoice_total == 100
    labors = (
        await db.execute(select(InvoiceLabor).where(InvoiceLabor.sc_invoice_id == 999000010))
    ).scalars().all()
    materials = (
        await db.execute(
            select(InvoiceMaterial).where(InvoiceMaterial.sc_invoice_id == 999000010)
        )
    ).scalars().all()
    history = (
        await db.execute(
            select(InvoiceStatusHistory).where(
                InvoiceStatusHistory.sc_invoice_id == 999000010
            )
        )
    ).scalars().all()
    assert len(labors) == 1
    assert len(materials) == 1
    assert len(history) == 1


async def test_out_of_order_does_not_regress(db: AsyncSession) -> None:
    paid = _event(
        "InvoicePaid",
        _obj(999000020, "ITESTB", Status="OPEN", UpdatedDate="2026-06-10T12:00:00Z"),
    )
    approved = _event(
        "InvoiceApproved",
        _obj(999000020, "ITESTB", UpdatedDate="2026-06-10T11:00:00Z"),
    )
    await process_event(db, await _store(db, paid, object_id=999000020), sc_env=ENV)
    await process_event(db, await _store(db, approved, object_id=999000020), sc_env=ENV)

    inv = await _get_invoice(db, 999000020)
    assert inv is not None
    assert inv.status == "Paid"  # the older Approved event did not regress it
    history = (
        await db.execute(
            select(InvoiceStatusHistory).where(
                InvoiceStatusHistory.sc_invoice_id == 999000020
            )
        )
    ).scalars().all()
    assert len(history) == 2  # both transitions recorded


async def test_empty_arrays_do_not_wipe_line_items(db: AsyncSession) -> None:
    created = _event(
        "InvoiceCreated",
        _obj(
            999000030,
            "ITESTC",
            UpdatedDate="2026-06-10T10:00:00Z",
            Labors=[{"SkillLevel": 2, "Amount": 60}],
            Materials=[{"Description": "p", "Amount": 40}],
        ),
    )
    paid = _event(
        "InvoicePaid",
        _obj(999000030, "ITESTC", UpdatedDate="2026-06-10T11:00:00Z", Labors=[], Materials=[]),
    )
    await process_event(db, await _store(db, created, object_id=999000030), sc_env=ENV)
    await process_event(db, await _store(db, paid, object_id=999000030), sc_env=ENV)

    labors = (
        await db.execute(select(InvoiceLabor).where(InvoiceLabor.sc_invoice_id == 999000030))
    ).scalars().all()
    assert len(labors) == 1  # the empty array on the Paid event left them intact


async def test_voided_uses_event_type_status(db: AsyncSession) -> None:
    body = _event("InvoiceVoided", _obj(999000040, "ITESTD", Status="OPEN"))
    await process_event(db, await _store(db, body, object_id=999000040), sc_env=ENV)
    inv = await _get_invoice(db, 999000040)
    assert inv is not None
    assert inv.status == "Void"  # EventType wins over the payload's OPEN


async def test_unknown_event_type_dead_letters(db: AsyncSession) -> None:
    body = _event("InvoiceFlibbertigibbet", _obj(999000050, "ITESTE"))
    eid = await _store(db, body, object_id=999000050)
    assert await process_event(db, eid, sc_env=ENV) == "dead_letter"
    ev = await db.get(WebhookEvent, eid)
    assert ev is not None and ev.status == "dead_letter" and ev.error


async def test_malformed_json_dead_letters(db: AsyncSession) -> None:
    eid = await _store(db, b"this is not json", object_id=999000060)
    assert await process_event(db, eid, sc_env=ENV) == "dead_letter"
    ev = await db.get(WebhookEvent, eid)
    assert ev is not None and ev.status == "dead_letter"


async def test_work_order_integration_paid(db: AsyncSession) -> None:
    wo = WorkOrder(
        sc_work_order_id=TEST_WO,
        sc_number="ITESTWO",
        primary_status="COMPLETED",
        extended_status="CONFIRMED",
    )
    db.add(wo)
    await db.commit()

    body = _event(
        "InvoicePaid",
        _obj(
            999000070,
            "ITESTPAID",
            WoTrackingNumber=TEST_WO,
            PaidDate="2026-06-09T00:00:00Z",
            UpdatedDate="2026-06-09T00:00:00Z",
        ),
    )
    await process_event(db, await _store(db, body, object_id=999000070), sc_env=ENV)

    refreshed = (
        await db.execute(select(WorkOrder).where(WorkOrder.sc_work_order_id == TEST_WO))
    ).scalar_one()
    await db.refresh(refreshed)
    assert refreshed.sc_invoice_status == "Paid"
    assert refreshed.sc_invoice_number == "ITESTPAID"
    assert refreshed.sc_paid_at is not None
    assert refreshed.brenk_paid_at is not None  # auto-populated since it was empty
