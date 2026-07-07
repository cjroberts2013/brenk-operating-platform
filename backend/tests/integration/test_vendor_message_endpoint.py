"""Integration test for GET /work-orders/{id}/vendor-message.

Seeds a WO + location (with an active gate code) + an assigned vendor in
the dev DB (ids >= 999003000, cleaned on teardown). The SC attachments
call is monkeypatched — no real SC traffic.
"""

from collections.abc import AsyncGenerator

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.v1.endpoints import work_orders as wo_endpoints
from app.core.config import get_settings
from app.db.session import get_async_db
from app.main import app
from app.models.work_order import Client, GateCode, Location, Vendor, WorkOrder
from app.services.servicechannel.client import ServiceChannelClient

SC_BASE = 999003000


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

    async def _cleanup() -> None:
        async with factory() as session:
            # Delete by EXACT seeded id — real SC ids run into the billions,
            # well above SC_BASE, so a `>=` here would scoop up real data.
            # WOs first (they FK location/vendor/client); deleting the
            # location cascades its gate_codes (FK ondelete=CASCADE), but
            # clear them explicitly too.
            await session.execute(delete(WorkOrder).where(WorkOrder.sc_work_order_id == SC_BASE))
            await session.execute(delete(GateCode).where(GateCode.code == "1234#TEST"))
            await session.execute(delete(Location).where(Location.sc_location_id == SC_BASE))
            await session.execute(delete(Vendor).where(Vendor.sc_provider_id == SC_BASE))
            await session.execute(delete(Client).where(Client.sc_subscriber_id == SC_BASE))
            await session.commit()

    app.dependency_overrides[get_async_db] = _override
    await _cleanup()  # clear any rows a prior aborted run left behind
    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", headers=auth_headers
        ) as ac:
            yield ac, factory
    finally:
        app.dependency_overrides.pop(get_async_db, None)
        await _cleanup()
        await engine.dispose()


async def _seed(
    factory: async_sessionmaker, *, vendor_email: str | None = "larry@example.com"
) -> int:
    async with factory() as s:
        client = Client(sc_subscriber_id=SC_BASE, name="SC Test Client")
        s.add(client)
        await s.flush()
        loc = Location(
            sc_location_id=SC_BASE,
            client_id=client.id,
            store_id="0751",
            name="0751 CUBESMART TX AUSTIN EAST STASSNEY LANE",
            raw_data={
                "Address1": "4900 East Stassney Lane",
                "City": "Austin",
                "State": "TX",
                "Zip": "78744",
            },
        )
        s.add(loc)
        await s.flush()
        s.add(GateCode(location_id=loc.id, code="1234#TEST", label="front gate", is_active=True))
        vendor = Vendor(
            sc_provider_id=SC_BASE,
            name="Larry's Locksmith",
            phone="+15125551212",
            email=vendor_email,
            contact_preference="email",
        )
        s.add(vendor)
        await s.flush()
        wo = WorkOrder(
            sc_work_order_id=SC_BASE,
            sc_number="343852740",
            primary_status="IN PROGRESS",
            description="Front gate motor not responding.",
            location_id=loc.id,
            client_id=client.id,
            assigned_vendor_id=vendor.id,
            attachments_count=1,
        )
        s.add(wo)
        await s.commit()
        return wo.id


async def test_vendor_message_composed(harness, monkeypatch) -> None:
    ac, factory = harness
    wo_id = await _seed(factory)

    async def fake_attachments(self, sc_id):
        return [{"Id": 1, "Name": "IMG_9872.jpeg"}]

    monkeypatch.setattr(ServiceChannelClient, "get_work_order_attachments", fake_attachments)

    resp = await ac.get(f"/api/v1/work-orders/{wo_id}/vendor-message")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["to_phone"] == "+15125551212"
    assert body["to_email"] == "larry@example.com"
    assert body["contact_preference"] == "email"
    assert body["photo_count"] == 1

    msg = body["body"]
    assert "WO #: 343852740" in msg
    assert "0751" in msg
    assert "4900 East Stassney Lane, Austin, TX 78744" in msg
    assert "Gate code: 1234#TEST (front gate)" in msg
    assert "Front gate motor not responding." in msg
    assert "Photos: 1 photo attached — IMG_9872.jpeg" in msg
    assert body["subject"].startswith("Brenk WO 343852740 — 0751")


async def test_vendor_message_attachments_best_effort(harness, monkeypatch) -> None:
    ac, factory = harness
    wo_id = await _seed(factory)

    async def boom(self, sc_id):
        raise RuntimeError("SC down")

    monkeypatch.setattr(ServiceChannelClient, "get_work_order_attachments", boom)

    resp = await ac.get(f"/api/v1/work-orders/{wo_id}/vendor-message")
    # SC failure must not break the message — it just drops the photo names.
    assert resp.status_code == 200, resp.text
    assert "Photos: none" in resp.json()["body"]
    assert resp.json()["photo_count"] == 0


async def test_vendor_message_unknown_wo_404(harness) -> None:
    ac, _ = harness
    resp = await ac.get("/api/v1/work-orders/999999999/vendor-message")
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# Email send
# --------------------------------------------------------------------------- #
async def test_send_vendor_email_success(harness, monkeypatch) -> None:
    ac, factory = harness
    wo_id = await _seed(factory)

    async def fake_attachments(self, sc_id):
        return [{"Id": 1, "Name": "IMG_9872.jpeg", "Uri": "https://sc/blob?sig=x"}]

    async def fake_bytes(self, uri):
        return b"\xff\xd8\xffJPEG", "image/jpeg"

    sent: dict = {}

    async def fake_send_email(**kwargs):
        sent.update(kwargs)
        return True

    monkeypatch.setattr(ServiceChannelClient, "get_work_order_attachments", fake_attachments)
    monkeypatch.setattr(ServiceChannelClient, "fetch_attachment_bytes", fake_bytes)
    monkeypatch.setattr(wo_endpoints, "send_email", fake_send_email)

    resp = await ac.post(f"/api/v1/work-orders/{wo_id}/send-vendor-email")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["sent"] is True
    assert body["to_email"] == "larry@example.com"
    assert body["photos_attached"] == 1

    # The email went to the vendor, FROM the workorder mailbox, reply-to
    # Daryl, with the photo attached.
    assert sent["to"] == "larry@example.com"
    assert sent["from_email"] == get_settings().VENDOR_FROM_EMAIL
    assert "workorder@brenkfacilityservices.com" in sent["from_email"]
    assert sent["reply_to"] == get_settings().QUOTE_TO_EMAIL
    assert "343852740" in sent["text"]
    assert "Gate code: 1234#TEST (front gate)" in sent["text"]
    assert len(sent["attachments"]) == 1
    assert sent["attachments"][0]["filename"] == "IMG_9872.jpeg"
    assert sent["attachments"][0]["content"]  # base64 present

    # notified timestamp stamped.
    async with factory() as s:
        wo = (await s.execute(select(WorkOrder).where(WorkOrder.id == wo_id))).scalar_one()
        assert wo.brenk_vendor_notified_at is not None


async def test_send_vendor_email_body_never_claims_unfetchable_photos(harness, monkeypatch) -> None:
    """SC listed a photo but its bytes 404 (e.g. expired/missing blob): the
    email must still send, with a body that says the photo couldn't attach —
    never '1 photo attached' for a photo the vendor won't get."""
    ac, factory = harness
    wo_id = await _seed(factory)

    async def fake_attachments(self, sc_id):
        return [{"Id": 1, "Name": "IMG_9872.jpeg", "Uri": "https://sc/blob?sig=x"}]

    async def broken_bytes(self, uri):
        raise RuntimeError("404 BlobNotFound")

    sent: dict = {}

    async def fake_send_email(**kwargs):
        sent.update(kwargs)
        return True

    monkeypatch.setattr(ServiceChannelClient, "get_work_order_attachments", fake_attachments)
    monkeypatch.setattr(ServiceChannelClient, "fetch_attachment_bytes", broken_bytes)
    monkeypatch.setattr(wo_endpoints, "send_email", fake_send_email)

    resp = await ac.post(f"/api/v1/work-orders/{wo_id}/send-vendor-email")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["photos_attached"] == 0
    assert body["photos_total"] == 1

    assert sent.get("attachments") is None
    assert "attached" not in sent["text"].split("Photos:")[1].split("\n")[0] or (
        "couldn't attach" in sent["text"]
    )
    assert "Photos: 1 photo on file — couldn't attach" in sent["text"]


async def test_send_vendor_email_stamps_assignment_notified(harness, monkeypatch) -> None:
    """With a junction assignment, the notified stamp lives on the assignment
    row (so a later assignment op's primary-resync can't wipe it)."""
    ac, factory = harness
    wo_id = await _seed(factory)

    from app.models.work_order import WoVendorAssignment

    async with factory() as s:
        wo = (await s.execute(select(WorkOrder).where(WorkOrder.id == wo_id))).scalar_one()
        s.add(WoVendorAssignment(work_order_id=wo.id, vendor_id=wo.assigned_vendor_id))
        await s.commit()

    async def no_attachments(self, sc_id):
        return []

    async def fake_send_email(**kwargs):
        return True

    monkeypatch.setattr(ServiceChannelClient, "get_work_order_attachments", no_attachments)
    monkeypatch.setattr(wo_endpoints, "send_email", fake_send_email)

    resp = await ac.post(f"/api/v1/work-orders/{wo_id}/send-vendor-email")
    assert resp.status_code == 200, resp.text

    async with factory() as s:
        wo = (await s.execute(select(WorkOrder).where(WorkOrder.id == wo_id))).scalar_one()
        assignment = (
            await s.execute(
                select(WoVendorAssignment).where(WoVendorAssignment.work_order_id == wo.id)
            )
        ).scalar_one()
        assert assignment.notified_at is not None
        assert wo.brenk_vendor_notified_at is not None  # mirrored by resync


async def test_send_vendor_email_no_email_400(harness, monkeypatch) -> None:
    ac, factory = harness
    wo_id = await _seed(factory, vendor_email=None)

    async def fake_send_email(**kwargs):  # should never be called
        raise AssertionError("send_email must not run without a vendor email")

    monkeypatch.setattr(wo_endpoints, "send_email", fake_send_email)
    resp = await ac.post(f"/api/v1/work-orders/{wo_id}/send-vendor-email")
    assert resp.status_code == 400
    assert "no email" in resp.json()["detail"].lower()


async def test_send_vendor_email_invalid_email_400(harness, monkeypatch) -> None:
    ac, factory = harness
    wo_id = await _seed(factory, vendor_email="not-an-email")

    async def fake_send_email(**kwargs):  # should never be called
        raise AssertionError("send_email must not run for an invalid address")

    monkeypatch.setattr(wo_endpoints, "send_email", fake_send_email)
    resp = await ac.post(f"/api/v1/work-orders/{wo_id}/send-vendor-email")
    assert resp.status_code == 400
    assert "valid" in resp.json()["detail"].lower()


async def test_send_vendor_email_failure_502(harness, monkeypatch) -> None:
    ac, factory = harness
    wo_id = await _seed(factory)

    async def no_attachments(self, sc_id):
        return []

    async def fake_send_email(**kwargs):
        return False  # Resend rejected / not configured

    monkeypatch.setattr(ServiceChannelClient, "get_work_order_attachments", no_attachments)
    monkeypatch.setattr(wo_endpoints, "send_email", fake_send_email)

    resp = await ac.post(f"/api/v1/work-orders/{wo_id}/send-vendor-email")
    assert resp.status_code == 502

    # A failed send must NOT stamp notified.
    async with factory() as s:
        wo = (await s.execute(select(WorkOrder).where(WorkOrder.id == wo_id))).scalar_one()
        assert wo.brenk_vendor_notified_at is None


async def test_send_vendor_email_unknown_wo_404(harness) -> None:
    ac, _ = harness
    resp = await ac.post("/api/v1/work-orders/999999999/send-vendor-email")
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# SMS send
# --------------------------------------------------------------------------- #
async def test_send_vendor_sms_success(harness, monkeypatch) -> None:
    ac, factory = harness
    wo_id = await _seed(factory)

    async def fake_attachments(self, sc_id):
        return [
            {"Id": 1, "Name": "IMG_1.jpeg", "Uri": "https://blob/1?sig=a"},
            {"Id": 2, "Name": "report.pdf", "Uri": "https://blob/2?sig=b"},
            {"Id": 3, "Name": "IMG_3.jpeg", "Uri": "https://blob/3?sig=c"},
        ]

    async def fake_bytes(self, uri):
        if uri.startswith("https://blob/2"):
            return b"%PDF-", "application/pdf"  # not MMS-able, skipped
        if uri.startswith("https://blob/3"):
            raise RuntimeError("404 BlobNotFound")  # missing blob, skipped
        return b"\xff\xd8\xffJPEG", "image/jpeg"

    sent: dict = {}

    async def fake_send_sms(**kwargs):
        sent.update(kwargs)
        return True

    monkeypatch.setattr(ServiceChannelClient, "get_work_order_attachments", fake_attachments)
    monkeypatch.setattr(ServiceChannelClient, "fetch_attachment_bytes", fake_bytes)
    monkeypatch.setattr(wo_endpoints, "send_sms", fake_send_sms)

    resp = await ac.post(f"/api/v1/work-orders/{wo_id}/send-vendor-sms")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["sent"] is True
    assert body["to_phone"] == "+15125551212"
    assert body["photos_attached"] == 1  # only the fetchable jpeg
    assert body["photos_total"] == 3

    # Only the verified image rides along as MMS media.
    assert sent["to"] == "+15125551212"
    assert sent["media_urls"] == ["https://blob/1?sig=a"]
    # The body claims exactly what attached, and flags the rest.
    assert "1 photo attached — IMG_1.jpeg" in sent["body"]
    assert "2 more couldn't be attached" in sent["body"]
    assert "Gate code: 1234#TEST (front gate)" in sent["body"]
    # A2P compliance suffix on texts only — must match the campaign samples.
    assert sent["body"].endswith("Reply STOP to opt out.")

    # notified timestamp stamped.
    async with factory() as s:
        wo = (await s.execute(select(WorkOrder).where(WorkOrder.id == wo_id))).scalar_one()
        assert wo.brenk_vendor_notified_at is not None


async def test_send_vendor_sms_normalizes_loose_phone(harness, monkeypatch) -> None:
    ac, factory = harness
    wo_id = await _seed(factory)
    async with factory() as s:
        vendor = (
            await s.execute(select(Vendor).where(Vendor.sc_provider_id == SC_BASE))
        ).scalar_one()
        vendor.phone = "(512) 555-1212"
        await s.commit()

    async def no_attachments(self, sc_id):
        return []

    sent: dict = {}

    async def fake_send_sms(**kwargs):
        sent.update(kwargs)
        return True

    monkeypatch.setattr(ServiceChannelClient, "get_work_order_attachments", no_attachments)
    monkeypatch.setattr(wo_endpoints, "send_sms", fake_send_sms)

    resp = await ac.post(f"/api/v1/work-orders/{wo_id}/send-vendor-sms")
    assert resp.status_code == 200, resp.text
    assert resp.json()["to_phone"] == "+15125551212"
    assert sent["to"] == "+15125551212"


async def test_send_vendor_sms_no_phone_400(harness, monkeypatch) -> None:
    ac, factory = harness
    wo_id = await _seed(factory)
    async with factory() as s:
        vendor = (
            await s.execute(select(Vendor).where(Vendor.sc_provider_id == SC_BASE))
        ).scalar_one()
        vendor.phone = None
        await s.commit()

    async def fake_send_sms(**kwargs):  # should never be called
        raise AssertionError("send_sms must not run without a phone")

    monkeypatch.setattr(wo_endpoints, "send_sms", fake_send_sms)
    resp = await ac.post(f"/api/v1/work-orders/{wo_id}/send-vendor-sms")
    assert resp.status_code == 400
    assert "no phone" in resp.json()["detail"].lower()


async def test_send_vendor_sms_bad_phone_400(harness, monkeypatch) -> None:
    ac, factory = harness
    wo_id = await _seed(factory)
    async with factory() as s:
        vendor = (
            await s.execute(select(Vendor).where(Vendor.sc_provider_id == SC_BASE))
        ).scalar_one()
        vendor.phone = "call the office"
        await s.commit()

    async def fake_send_sms(**kwargs):  # should never be called
        raise AssertionError("send_sms must not run for an unusable phone")

    monkeypatch.setattr(wo_endpoints, "send_sms", fake_send_sms)
    resp = await ac.post(f"/api/v1/work-orders/{wo_id}/send-vendor-sms")
    assert resp.status_code == 400
    assert "textable" in resp.json()["detail"].lower()


async def test_send_vendor_sms_failure_502(harness, monkeypatch) -> None:
    ac, factory = harness
    wo_id = await _seed(factory)

    async def no_attachments(self, sc_id):
        return []

    async def fake_send_sms(**kwargs):
        return False  # Twilio rejected / not configured

    monkeypatch.setattr(ServiceChannelClient, "get_work_order_attachments", no_attachments)
    monkeypatch.setattr(wo_endpoints, "send_sms", fake_send_sms)

    resp = await ac.post(f"/api/v1/work-orders/{wo_id}/send-vendor-sms")
    assert resp.status_code == 502

    # A failed send must NOT stamp notified.
    async with factory() as s:
        wo = (await s.execute(select(WorkOrder).where(WorkOrder.id == wo_id))).scalar_one()
        assert wo.brenk_vendor_notified_at is None
