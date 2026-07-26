"""Integration tests for POST /api/v1/webhooks/twilio (inbound vendor SMS).

Seeds a vendor (+ optional WO/assignment for context) in the dev DB, posts
a Twilio-signed form body, and asserts the reply is logged to sms_replies
and forwarded. send_sms is monkeypatched — no real Twilio traffic.
"""

import base64
import hashlib
import hmac
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.v1.endpoints import webhooks as wh
from app.core.config import get_settings
from app.db.session import get_async_db
from app.main import app
from app.models.work_order import (
    Client,
    Location,
    SmsReply,
    Vendor,
    WorkOrder,
    WoVendorAssignment,
)

SC_BASE = 999004000
VENDOR_PHONE = "+15125551212"
WEBHOOK_URL = "http://test/api/v1/webhooks/twilio"
AUTH_TOKEN = "test-auth-token-123"
REPLY_TO = "+19995550100"


def _sign(params: dict[str, str]) -> str:
    base = WEBHOOK_URL
    for k in sorted(params):
        base += k + params[k]
    return base64.b64encode(
        hmac.new(AUTH_TOKEN.encode(), base.encode(), hashlib.sha1).digest()
    ).decode()


@pytest.fixture
async def harness(monkeypatch) -> AsyncGenerator[tuple[httpx.AsyncClient, async_sessionmaker]]:
    settings = get_settings()
    monkeypatch.setattr(settings, "TWILIO_WEBHOOK_URL", WEBHOOK_URL)
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", AUTH_TOKEN)
    monkeypatch.setattr(settings, "VENDOR_REPLY_TO_PHONE", REPLY_TO)

    engine = create_async_engine(settings.DATABASE_URL_ASYNC, poolclass=NullPool)
    factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )

    async def _override() -> AsyncGenerator[AsyncSession]:
        async with factory() as s:
            yield s

    async def _cleanup() -> None:
        async with factory() as s:
            await s.execute(delete(SmsReply).where(SmsReply.from_number == VENDOR_PHONE))
            await s.execute(
                delete(WoVendorAssignment).where(
                    WoVendorAssignment.vendor_id.in_(
                        select(Vendor.id).where(Vendor.sc_provider_id == SC_BASE)
                    )
                )
            )
            await s.execute(delete(WorkOrder).where(WorkOrder.sc_work_order_id == SC_BASE))
            await s.execute(delete(Vendor).where(Vendor.sc_provider_id == SC_BASE))
            await s.execute(delete(Location).where(Location.sc_location_id == SC_BASE))
            await s.execute(delete(Client).where(Client.sc_subscriber_id == SC_BASE))
            await s.commit()

    app.dependency_overrides[get_async_db] = _override
    await _cleanup()
    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac, factory
    finally:
        app.dependency_overrides.pop(get_async_db, None)
        await _cleanup()
        await engine.dispose()


async def _seed_vendor_with_wo(factory) -> None:
    async with factory() as s:
        client = Client(sc_subscriber_id=SC_BASE, name="SC Test Client")
        s.add(client)
        await s.flush()
        loc = Location(
            sc_location_id=SC_BASE, client_id=client.id, store_id="0751", name="STASSNEY"
        )
        s.add(loc)
        vendor = Vendor(sc_provider_id=SC_BASE, name="Larry's Locksmith", phone="(512) 555-1212")
        s.add(vendor)
        await s.flush()
        wo = WorkOrder(
            sc_work_order_id=SC_BASE,
            sc_number="343852740",
            primary_status="IN PROGRESS",
            location_id=loc.id,
            client_id=client.id,
        )
        s.add(wo)
        await s.flush()
        s.add(
            WoVendorAssignment(
                work_order_id=wo.id, vendor_id=vendor.id, notified_at=datetime.now(UTC)
            )
        )
        await s.commit()


async def _post(ac, params: dict[str, str], *, sign: bool = True) -> httpx.Response:
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if sign:
        headers["X-Twilio-Signature"] = _sign(params)
    return await ac.post("/api/v1/webhooks/twilio", data=params, headers=headers)


async def test_normal_reply_forwarded_and_logged(harness, monkeypatch) -> None:
    ac, factory = harness
    await _seed_vendor_with_wo(factory)

    sent: dict = {}

    async def fake_send_sms(**kwargs):
        sent.update(kwargs)
        return True

    monkeypatch.setattr(wh, "send_sms", fake_send_sms)

    params = {
        "From": VENDOR_PHONE,
        "To": "+18555144246",
        "Body": "Can be there at 2pm",
        "MessageSid": "SM_reply_1",
        "NumMedia": "0",
    }
    resp = await _post(ac, params)
    assert resp.status_code == 200
    assert "<Response>" in resp.text  # empty TwiML, no auto-reply

    # Forwarded to the operator with vendor + WO context.
    assert sent["to"] == REPLY_TO
    assert "Larry's Locksmith replied" in sent["body"]
    assert "343852740" in sent["body"]
    assert "Can be there at 2pm" in sent["body"]

    # Logged to history, matched to the vendor, not an opt-out.
    async with factory() as s:
        row = (
            await s.execute(select(SmsReply).where(SmsReply.twilio_message_sid == "SM_reply_1"))
        ).scalar_one()
        assert row.from_number == VENDOR_PHONE
        assert row.vendor_id is not None
        assert row.is_opt_out is False
        assert row.forwarded is True


async def test_opt_out_reply_sends_alert(harness, monkeypatch) -> None:
    ac, factory = harness
    await _seed_vendor_with_wo(factory)

    sent: dict = {}

    async def fake_send_sms(**kwargs):
        sent.update(kwargs)
        return True

    monkeypatch.setattr(wh, "send_sms", fake_send_sms)

    params = {"From": VENDOR_PHONE, "To": "+18555144246", "Body": "STOP", "MessageSid": "SM_stop_1"}
    resp = await _post(ac, params)
    assert resp.status_code == 200
    assert "opted OUT" in sent["body"]
    assert "Larry's Locksmith" in sent["body"]

    async with factory() as s:
        row = (
            await s.execute(select(SmsReply).where(SmsReply.twilio_message_sid == "SM_stop_1"))
        ).scalar_one()
        assert row.is_opt_out is True


async def test_unknown_number_still_forwards_and_logs(harness, monkeypatch) -> None:
    ac, _factory = harness  # no vendor seeded

    sent: dict = {}

    async def fake_send_sms(**kwargs):
        sent.update(kwargs)
        return True

    monkeypatch.setattr(wh, "send_sms", fake_send_sms)

    params = {
        "From": VENDOR_PHONE,
        "To": "+18555144246",
        "Body": "who is this?",
        "MessageSid": "SM_unk_1",
    }
    resp = await _post(ac, params)
    assert resp.status_code == 200
    assert "unrecognized number" in sent["body"]


async def test_invalid_signature_403(harness, monkeypatch) -> None:
    ac, _factory = harness

    async def must_not_send(**kwargs):
        raise AssertionError("must not forward on bad signature")

    monkeypatch.setattr(wh, "send_sms", must_not_send)

    params = {"From": VENDOR_PHONE, "Body": "hi", "MessageSid": "SM_bad_1"}
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Twilio-Signature": "not-a-valid-signature",
    }
    resp = await ac.post("/api/v1/webhooks/twilio", data=params, headers=headers)
    assert resp.status_code == 403
