"""Integration tests for the invoice-centric list endpoint filters.

Creates synthetic invoices sharing a unique `trade` token so `q` isolates
them from any other rows in the dev DB; asserts status_group, search, and
pagination. Cleans up on teardown.
"""

from collections.abc import AsyncGenerator

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

ENV = get_settings().SC_ENVIRONMENT
# Unique token shared by all test rows so q-search isolates exactly them.
TOKEN = "ZZLISTTEST7788"
ROWS = [
    ("ILIST-A", "Approved"),
    ("ILIST-B", "Paid"),
    ("ILIST-C", "Paid"),
    ("ILIST-D", "Rejected"),
]


@pytest.fixture
async def client(
    auth_headers: dict[str, str],
) -> AsyncGenerator[httpx.AsyncClient]:
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL_ASYNC, poolclass=NullPool)
    factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )
    async with factory() as s:
        for number, status in ROWS:
            s.add(
                Invoice(
                    sc_env=ENV,
                    invoice_number=number,
                    status=status,
                    trade=TOKEN,
                    source="backfill",
                )
            )
        await s.commit()

    async def _override() -> AsyncGenerator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_async_db] = _override
    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", headers=auth_headers
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_async_db, None)
        async with factory() as s:
            await s.execute(delete(Invoice).where(Invoice.trade == TOKEN))
            await s.commit()
        await engine.dispose()


async def _get(client: httpx.AsyncClient, **params: object) -> dict:
    r = await client.get("/api/v1/invoices/", params=params)
    assert r.status_code == 200, r.text
    return r.json()


async def test_q_isolates_test_rows(client: httpx.AsyncClient) -> None:
    body = await _get(client, q=TOKEN, page_size=50)
    assert body["total"] == 4
    assert {i["invoice_number"] for i in body["items"]} == {n for n, _ in ROWS}


async def test_status_group_awaiting(client: httpx.AsyncClient) -> None:
    body = await _get(client, q=TOKEN, status_group="awaiting")
    assert body["total"] == 1
    assert body["items"][0]["invoice_number"] == "ILIST-A"


async def test_status_group_paid(client: httpx.AsyncClient) -> None:
    body = await _get(client, q=TOKEN, status_group="paid")
    assert body["total"] == 2
    assert {i["invoice_number"] for i in body["items"]} == {"ILIST-B", "ILIST-C"}


async def test_status_group_rejected(client: httpx.AsyncClient) -> None:
    body = await _get(client, q=TOKEN, status_group="rejected")
    assert body["total"] == 1
    assert body["items"][0]["invoice_number"] == "ILIST-D"


async def test_q_matches_invoice_number(client: httpx.AsyncClient) -> None:
    body = await _get(client, q="ILIST-C")
    assert {i["invoice_number"] for i in body["items"]} == {"ILIST-C"}


async def test_pagination(client: httpx.AsyncClient) -> None:
    p1 = await _get(client, q=TOKEN, page=1, page_size=2)
    p2 = await _get(client, q=TOKEN, page=2, page_size=2)
    assert p1["total"] == 4 and p2["total"] == 4
    assert len(p1["items"]) == 2 and len(p2["items"]) == 2
    # No overlap between pages.
    assert not ({i["invoice_number"] for i in p1["items"]} &
                {i["invoice_number"] for i in p2["items"]})
