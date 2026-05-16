"""Integration tests for /api/v1/work-orders.

These tests run against the real dev Supabase database — they assume the
sync worker has populated at least one work order, which is true after
running `scripts/test_sync.py` at least once. If the DB is empty the
tests skip rather than fail.

Uses `httpx.AsyncClient` with an ASGI transport (not FastAPI's sync
`TestClient`) because the latter spins up a new event loop per request,
which conflicts with the asyncpg connection pool that's tied to the
first loop.
"""

from collections.abc import AsyncGenerator

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.db.session import get_async_db
from app.main import app


@pytest.fixture
async def client() -> AsyncGenerator[httpx.AsyncClient]:
    """ASGI test client with a NullPool-backed DB engine.

    The module-level async engine in app.db.session caches connections tied
    to the event loop of the first test, which then go stale on subsequent
    tests' loops. Overriding get_async_db with a per-test engine using
    NullPool sidesteps that — each request opens (and closes) its own
    asyncpg connection.
    """
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
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_async_db, None)
        await test_engine.dispose()


async def _list(client: httpx.AsyncClient, **params) -> dict:
    response = await client.get("/api/v1/work-orders/", params=params)
    assert response.status_code == 200, response.text
    return response.json()


async def test_list_returns_paginated_envelope(client: httpx.AsyncClient) -> None:
    body = await _list(client, page_size=5)
    assert set(body.keys()) == {"items", "total", "page", "page_size"}
    assert body["page"] == 1
    assert body["page_size"] == 5
    assert isinstance(body["total"], int)
    if body["total"] == 0:
        pytest.skip("dev DB has no work orders; run scripts/test_sync.py first")
    assert len(body["items"]) <= 5


async def test_list_item_shape(client: httpx.AsyncClient) -> None:
    body = await _list(client, page_size=1)
    if body["total"] == 0:
        pytest.skip("dev DB has no work orders")
    item = body["items"][0]
    for key in ("id", "sc_work_order_id", "sc_number", "primary_status"):
        assert key in item, f"missing {key} in summary"
    for key in ("trade", "location", "client"):
        assert key in item


async def test_list_pagination_walks_pages(client: httpx.AsyncClient) -> None:
    page_one = await _list(client, page=1, page_size=2)
    if page_one["total"] < 3:
        pytest.skip("need at least 3 WOs to test pagination across pages")
    page_two = await _list(client, page=2, page_size=2)
    assert page_two["page"] == 2
    ids_one = {item["id"] for item in page_one["items"]}
    ids_two = {item["id"] for item in page_two["items"]}
    assert ids_one.isdisjoint(ids_two), "pages should not overlap"


async def test_list_filter_by_status(client: httpx.AsyncClient) -> None:
    body = await _list(client, status="COMPLETED", page_size=5)
    for item in body["items"]:
        assert item["primary_status"] == "COMPLETED"


async def test_detail_returns_full_shape(client: httpx.AsyncClient) -> None:
    listed = await _list(client, page_size=1)
    if listed["total"] == 0:
        pytest.skip("dev DB has no work orders")
    wo_id = listed["items"][0]["id"]

    response = await client.get(f"/api/v1/work-orders/{wo_id}")
    assert response.status_code == 200, response.text
    detail = response.json()
    for key in ("description", "currency_code", "is_invoiced", "last_synced_at"):
        assert key in detail


async def test_detail_404_for_unknown_id(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/work-orders/999999999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


async def test_invalid_page_size_rejected(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/work-orders/", params={"page_size": 9999})
    assert response.status_code == 422
