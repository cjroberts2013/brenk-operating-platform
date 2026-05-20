"""Integration tests for /api/v1/trades."""

from collections.abc import AsyncGenerator

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.db.session import get_async_db
from app.main import app


@pytest.fixture
async def client(auth_headers: dict[str, str]) -> AsyncGenerator[httpx.AsyncClient]:
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


async def _delete_trade(trade_id: int) -> None:
    """Hard-delete a trade row so tests stay self-contained."""
    settings = get_settings()
    eng = create_async_engine(settings.DATABASE_URL_ASYNC, poolclass=NullPool)
    async with eng.connect() as conn:
        await conn.execute(
            text("DELETE FROM vendor_trades WHERE trade_id = :id"), {"id": trade_id}
        )
        await conn.execute(text("DELETE FROM trades WHERE id = :id"), {"id": trade_id})
        await conn.commit()
    await eng.dispose()


async def test_list_trades_returns_alphabetical(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/trades/")
    assert response.status_code == 200
    items = response.json()
    assert isinstance(items, list)
    if len(items) > 1:
        names = [t["name"] for t in items]
        assert names == sorted(names)


async def test_create_trade(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/trades/", json={"name": "Solar Panels"}
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "Solar Panels"
    assert body["sc_trade_id"] is None
    await _delete_trade(body["id"])


async def test_create_trade_rejects_empty_name(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/v1/trades/", json={"name": ""})
    assert response.status_code == 422


async def test_create_trade_rejects_case_insensitive_duplicate(
    client: httpx.AsyncClient,
) -> None:
    first = await client.post("/api/v1/trades/", json={"name": "Acoustic Tiling"})
    assert first.status_code == 201
    trade_id = first.json()["id"]
    try:
        # Exact match → 409
        dup = await client.post("/api/v1/trades/", json={"name": "Acoustic Tiling"})
        assert dup.status_code == 409
        # Different case → still 409 (case-insensitive check)
        dup2 = await client.post("/api/v1/trades/", json={"name": "ACOUSTIC TILING"})
        assert dup2.status_code == 409
        assert "already exists" in dup2.json()["detail"]
    finally:
        await _delete_trade(trade_id)
