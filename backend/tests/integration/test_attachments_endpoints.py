"""Integration tests for the work-order attachments endpoints.

Hits the real dev DB with a synthetic WO (id >= 999002000, cleaned on
teardown). ServiceChannel is monkeypatched — tests never touch the real
SC API (per repo conventions).
"""

from collections.abc import AsyncGenerator

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.exceptions import ServiceChannelError
from app.db.session import get_async_db
from app.main import app
from app.models.work_order import WorkOrder
from app.services.servicechannel.client import ServiceChannelClient

TEST_WO_ID = 999002000

# A realistic SC attachments-list item. The `Uri` is a (fake) presigned SAS
# URL carrying a signature — it must never reach the client.
_SECRET_SIG = "OMiTYAdG8NmSsecretsig"
_SAMPLE_ATTACHMENT = {
    "Id": 336595642,
    "Name": "IMG_9872.jpeg",
    "Description": "front gate",
    "TimeStamp": "2026-06-20T18:33:52.842Z",
    "Uri": f"https://storage.servicechannel.com/workorders/abc?sv=2026-02-06&sig={_SECRET_SIG}",
    "NoteId": None,
    "Visibility": 0,
    "IsInvoiceDigitalCopy": False,
    "UploadBy": "rybarra@cubesmart.com",
}


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
            await session.execute(delete(WorkOrder).where(WorkOrder.sc_work_order_id >= TEST_WO_ID))
            await session.commit()
        await engine.dispose()


async def _make_wo(factory: async_sessionmaker) -> int:
    async with factory() as session:
        wo = WorkOrder(
            sc_work_order_id=TEST_WO_ID,
            sc_number="IATTACH1",
            primary_status="IN PROGRESS",
            extended_status="DISPATCH CONFIRMED",
        )
        session.add(wo)
        await session.commit()
        return wo.id


# --------------------------------------------------------------------------- #
# List
# --------------------------------------------------------------------------- #
async def test_list_maps_fields_and_hides_uri(harness, monkeypatch) -> None:
    ac, factory = harness
    wo_id = await _make_wo(factory)

    async def fake_list(self, sc_id):
        assert sc_id == TEST_WO_ID  # resolved our id → SC id
        return [_SAMPLE_ATTACHMENT]

    monkeypatch.setattr(ServiceChannelClient, "get_work_order_attachments", fake_list)

    resp = await ac.get(f"/api/v1/work-orders/{wo_id}/attachments")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    att = body[0]
    assert att["id"] == 336595642
    assert att["name"] == "IMG_9872.jpeg"
    assert att["description"] == "front gate"
    assert att["upload_by"] == "rybarra@cubesmart.com"
    assert att["is_invoice_digital_copy"] is False
    assert att["content_type"] == "image/jpeg"  # guessed from the file name
    # Confidentiality: the presigned Uri (and its signature) never leak.
    assert "uri" not in {k.lower() for k in att}
    assert _SECRET_SIG not in resp.text
    assert "servicechannel.com" not in resp.text


async def test_list_empty(harness, monkeypatch) -> None:
    ac, factory = harness
    wo_id = await _make_wo(factory)

    async def fake_list(self, sc_id):
        return []

    monkeypatch.setattr(ServiceChannelClient, "get_work_order_attachments", fake_list)
    resp = await ac.get(f"/api/v1/work-orders/{wo_id}/attachments")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_unknown_wo_404(harness) -> None:
    ac, _ = harness
    resp = await ac.get("/api/v1/work-orders/999999999/attachments")
    assert resp.status_code == 404


async def test_list_sc_error_is_502(harness, monkeypatch) -> None:
    ac, factory = harness
    wo_id = await _make_wo(factory)

    async def fake_fail(self, sc_id):
        raise ServiceChannelError("SC API error: 504 NotAllowed")

    monkeypatch.setattr(ServiceChannelClient, "get_work_order_attachments", fake_fail)
    resp = await ac.get(f"/api/v1/work-orders/{wo_id}/attachments")
    assert resp.status_code == 502
    # Operator-facing message, not the raw SC error.
    assert "ServiceChannel" in resp.json()["detail"]
    assert "NotAllowed" not in resp.json()["detail"]


# --------------------------------------------------------------------------- #
# Download
# --------------------------------------------------------------------------- #
async def test_download_streams_with_headers(harness, monkeypatch) -> None:
    ac, factory = harness
    wo_id = await _make_wo(factory)

    async def fake_list(self, sc_id):
        return [_SAMPLE_ATTACHMENT]

    async def fake_bytes(self, uri):
        assert _SECRET_SIG in uri  # resolved the real Uri server-side
        return b"\xff\xd8\xff\xe0JPEGDATA", "image/jpeg"

    monkeypatch.setattr(ServiceChannelClient, "get_work_order_attachments", fake_list)
    monkeypatch.setattr(ServiceChannelClient, "fetch_attachment_bytes", fake_bytes)

    # Default: inline disposition.
    resp = await ac.get(f"/api/v1/work-orders/{wo_id}/attachments/336595642/download")
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("image/jpeg")
    assert resp.headers["content-disposition"] == 'inline; filename="IMG_9872.jpeg"'
    assert resp.content == b"\xff\xd8\xff\xe0JPEGDATA"

    # download=true forces an attachment disposition.
    resp2 = await ac.get(
        f"/api/v1/work-orders/{wo_id}/attachments/336595642/download",
        params={"download": "true"},
    )
    assert resp2.headers["content-disposition"] == 'attachment; filename="IMG_9872.jpeg"'


async def test_download_unknown_attachment_404(harness, monkeypatch) -> None:
    ac, factory = harness
    wo_id = await _make_wo(factory)

    async def fake_list(self, sc_id):
        return [_SAMPLE_ATTACHMENT]  # id 336595642 only

    monkeypatch.setattr(ServiceChannelClient, "get_work_order_attachments", fake_list)
    resp = await ac.get(f"/api/v1/work-orders/{wo_id}/attachments/111111/download")
    assert resp.status_code == 404


async def test_download_unknown_wo_404(harness) -> None:
    ac, _ = harness
    resp = await ac.get("/api/v1/work-orders/999999999/attachments/1/download")
    assert resp.status_code == 404


async def test_download_fetch_error_is_502(harness, monkeypatch) -> None:
    ac, factory = harness
    wo_id = await _make_wo(factory)

    async def fake_list(self, sc_id):
        return [_SAMPLE_ATTACHMENT]

    async def fake_fail(self, uri):
        raise ServiceChannelError("attachment fetch failed: 403 Forbidden")

    monkeypatch.setattr(ServiceChannelClient, "get_work_order_attachments", fake_list)
    monkeypatch.setattr(ServiceChannelClient, "fetch_attachment_bytes", fake_fail)
    resp = await ac.get(f"/api/v1/work-orders/{wo_id}/attachments/336595642/download")
    assert resp.status_code == 502
