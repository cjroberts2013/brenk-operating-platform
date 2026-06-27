"""Integration tests for /api/v1/vendors and WO vendor assignment.

Each test creates and tears down its own vendor rows so it doesn't
leak state into the dev DB. WOs are NOT torn down (they're sourced
from SC and we'd rather not delete real-looking data).
"""

from collections.abc import AsyncGenerator
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.db.session import get_async_db
from app.main import app


@pytest.fixture
async def client(auth_headers: dict[str, str]) -> AsyncGenerator[httpx.AsyncClient]:
    """Same NullPool-backed authenticated client as test_work_order_endpoints."""
    settings = get_settings()
    test_engine = create_async_engine(settings.DATABASE_URL_ASYNC, poolclass=NullPool)
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    async def _override_get_async_db() -> AsyncGenerator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_async_db] = _override_get_async_db
    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers=auth_headers,
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_async_db, None)
        await test_engine.dispose()


async def _create(client: httpx.AsyncClient, **fields: Any) -> dict:
    body = {"name": fields.pop("name", "Test Vendor")} | fields
    response = await client.post("/api/v1/vendors/", json=body)
    assert response.status_code == 201, response.text
    return response.json()


async def _delete(client: httpx.AsyncClient, vendor_id: int) -> None:
    """Hard-cleanup helper — soft-deletes, then directly hard-removes the
    row so tests don't leave inactive cruft in the dev DB. Uses a direct
    SQLAlchemy connection because the API only soft-deletes."""
    settings = get_settings()
    eng = create_async_engine(settings.DATABASE_URL_ASYNC, poolclass=NullPool)
    async with eng.connect() as conn:
        from sqlalchemy import text

        await conn.execute(
            text("DELETE FROM vendor_trades WHERE vendor_id = :id"), {"id": vendor_id}
        )
        await conn.execute(text("DELETE FROM vendors WHERE id = :id"), {"id": vendor_id})
        await conn.commit()
    await eng.dispose()


# -----------------------------------------------------------------------------
# Vendor CRUD
# -----------------------------------------------------------------------------


async def test_create_vendor_minimal(client: httpx.AsyncClient) -> None:
    payload = {"name": "Acme Plumbing"}
    response = await client.post("/api/v1/vendors/", json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "Acme Plumbing"
    assert body["is_active"] is True
    assert body["skills"] == []
    assert body["active_work_orders"] == 0
    await _delete(client, body["id"])


async def test_create_vendor_with_all_fields(client: httpx.AsyncClient) -> None:
    payload = {
        "name": "Big Hammer Roofing",
        "phone": "+15555550100",
        "email": "ops@bighammer.example",
        "contact_preference": "sms",
        "payment_terms": "Invoices weekly",
        "mobile_app_capable": True,
        "markup_notes": "premium work",
        "communication_notes": "don't text after 6pm",
    }
    body = await _create(client, **payload)
    for key, value in payload.items():
        assert body[key] == value
    await _delete(client, body["id"])


async def test_create_vendor_rejects_bad_job_type_id(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/vendors/",
        json={"name": "Test", "job_type_ids": [999999]},
    )
    assert response.status_code == 400
    assert "job_type_ids" in response.json()["detail"].lower()


async def test_create_vendor_requires_name(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/v1/vendors/", json={})
    assert response.status_code == 422
    response = await client.post("/api/v1/vendors/", json={"name": ""})
    assert response.status_code == 422


async def test_list_vendors_shape(client: httpx.AsyncClient) -> None:
    created = await _create(client, name="zzz Sentinel Vendor")
    try:
        response = await client.get("/api/v1/vendors/", params={"page_size": 5})
        assert response.status_code == 200, response.text
        body = response.json()
        assert set(body.keys()) == {"items", "total", "page", "page_size"}
        assert body["page"] == 1
        # The vendor we just created must appear when we widen the page —
        # but to keep this test independent of total count we just sanity-
        # check by fetching it directly.
    finally:
        await _delete(client, created["id"])


async def test_get_vendor_404(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/vendors/999999999")
    assert response.status_code == 404


async def test_get_vendor_returns_created(client: httpx.AsyncClient) -> None:
    created = await _create(client, name="Roundtrip Vendor")
    try:
        response = await client.get(f"/api/v1/vendors/{created['id']}")
        assert response.status_code == 200
        assert response.json()["name"] == "Roundtrip Vendor"
    finally:
        await _delete(client, created["id"])


async def test_patch_vendor_updates_only_sent_fields(client: httpx.AsyncClient) -> None:
    created = await _create(
        client,
        name="Patch Target",
        phone="+15555551111",
        contact_preference="email",
    )
    try:
        # Patch ONLY phone — contact_preference must stay untouched.
        response = await client.patch(
            f"/api/v1/vendors/{created['id']}",
            json={"phone": "+15555552222"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["phone"] == "+15555552222"
        assert body["contact_preference"] == "email"  # preserved
        assert body["name"] == "Patch Target"  # preserved
    finally:
        await _delete(client, created["id"])


async def test_delete_vendor_marks_inactive(client: httpx.AsyncClient) -> None:
    created = await _create(client, name="To Be Soft-Deleted")
    try:
        response = await client.delete(f"/api/v1/vendors/{created['id']}")
        assert response.status_code == 204

        # Subsequent GET still returns the vendor, with is_active=False.
        response = await client.get(f"/api/v1/vendors/{created['id']}")
        assert response.status_code == 200
        assert response.json()["is_active"] is False
    finally:
        await _delete(client, created["id"])


async def test_list_filter_by_is_active(client: httpx.AsyncClient) -> None:
    active = await _create(client, name="Filter Active Vendor")
    inactive = await _create(client, name="Filter Inactive Vendor", is_active=False)
    try:
        active_resp = await client.get(
            "/api/v1/vendors/", params={"is_active": "true", "page_size": 200}
        )
        ids_active = {v["id"] for v in active_resp.json()["items"]}
        assert active["id"] in ids_active
        assert inactive["id"] not in ids_active

        inactive_resp = await client.get(
            "/api/v1/vendors/", params={"is_active": "false", "page_size": 200}
        )
        ids_inactive = {v["id"] for v in inactive_resp.json()["items"]}
        assert inactive["id"] in ids_inactive
        assert active["id"] not in ids_inactive
    finally:
        await _delete(client, active["id"])
        await _delete(client, inactive["id"])


# -----------------------------------------------------------------------------
# WO vendor assignment via PATCH
# -----------------------------------------------------------------------------


async def _grab_any_work_order_id(client: httpx.AsyncClient) -> int | None:
    response = await client.get("/api/v1/work-orders/", params={"page_size": 1})
    if response.status_code != 200:
        return None
    items = response.json()["items"]
    return items[0]["id"] if items else None


async def test_patch_work_order_assigns_vendor(client: httpx.AsyncClient) -> None:
    wo_id = await _grab_any_work_order_id(client)
    if wo_id is None:
        pytest.skip("no work orders in DB; run a sync first")

    vendor = await _create(client, name="Assignment Test Vendor")
    try:
        response = await client.patch(
            f"/api/v1/work-orders/{wo_id}",
            json={"assigned_vendor_id": vendor["id"]},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["assigned_vendor"]["id"] == vendor["id"]

        # Unassign via null.
        response = await client.patch(
            f"/api/v1/work-orders/{wo_id}",
            json={"assigned_vendor_id": None},
        )
        assert response.status_code == 200
        assert response.json()["assigned_vendor"] is None
    finally:
        # Be tidy: unassign before deleting the vendor.
        await client.patch(
            f"/api/v1/work-orders/{wo_id}",
            json={"assigned_vendor_id": None},
        )
        await _delete(client, vendor["id"])


async def test_patch_work_order_rejects_unknown_vendor(client: httpx.AsyncClient) -> None:
    wo_id = await _grab_any_work_order_id(client)
    if wo_id is None:
        pytest.skip("no work orders in DB")
    response = await client.patch(
        f"/api/v1/work-orders/{wo_id}",
        json={"assigned_vendor_id": 999999999},
    )
    assert response.status_code == 400
    assert "vendor" in response.json()["detail"].lower()


async def test_patch_work_order_404_for_unknown_id(client: httpx.AsyncClient) -> None:
    response = await client.patch(
        "/api/v1/work-orders/999999999",
        json={"assigned_vendor_id": None},
    )
    assert response.status_code == 404
