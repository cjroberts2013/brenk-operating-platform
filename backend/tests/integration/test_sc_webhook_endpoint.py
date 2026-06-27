"""Integration tests for the SC webhook receiver.

Runs against the real dev Supabase DB (like the other integration tests).
Creates webhook_events rows with EventType prefixed `ITEST_` and deletes
them on teardown, so it leaves the DB as it found it.
"""

import base64
import hashlib
import hmac
import json
from collections.abc import AsyncGenerator

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.db.session import get_async_db
from app.main import app
from app.models.invoice import WebhookEvent

WEBHOOK_URL = "/api/v1/webhooks/servicechannel"
TEST_KEY = "brenk-webhook-test-key"


def _sign(body: bytes) -> str:
    return base64.b64encode(hmac.new(TEST_KEY.encode(), body, hashlib.sha256).digest()).decode()


@pytest.fixture
async def wh(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[tuple[httpx.AsyncClient, async_sessionmaker]]:
    """Unauthenticated ASGI client (the receiver is public) + a session
    factory for assertions, with a known signing key and row cleanup."""
    settings = get_settings()
    monkeypatch.setattr(settings, "SC_WEBHOOK_SIGNING_KEY", TEST_KEY)

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
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac, factory
    finally:
        app.dependency_overrides.pop(get_async_db, None)
        async with factory() as session:
            await session.execute(
                delete(WebhookEvent).where(WebhookEvent.event_type.like("ITEST_%"))
            )
            await session.commit()
        await engine.dispose()


async def test_reachability_get_returns_200(
    wh: tuple[httpx.AsyncClient, async_sessionmaker],
) -> None:
    ac, _ = wh
    resp = await ac.get(WEBHOOK_URL)
    assert resp.status_code == 200


async def test_empty_body_ping_acks_without_storing(
    wh: tuple[httpx.AsyncClient, async_sessionmaker],
) -> None:
    ac, factory = wh
    resp = await ac.post(WEBHOOK_URL, content=b"")
    assert resp.status_code == 200
    async with factory() as session:
        n = (
            (
                await session.execute(
                    select(WebhookEvent).where(WebhookEvent.event_type.like("ITEST_%"))
                )
            )
            .scalars()
            .all()
        )
        assert n == []  # ping stored nothing


async def test_invalid_signature_rejected_and_recorded(
    wh: tuple[httpx.AsyncClient, async_sessionmaker],
) -> None:
    ac, factory = wh
    body = json.dumps({"EventType": "ITEST_BadSig", "Object": {"Id": 999000001}}).encode()
    resp = await ac.post(WEBHOOK_URL, content=body, headers={"Sign-Data": "nope"})
    assert resp.status_code == 401
    async with factory() as session:
        row = (
            (
                await session.execute(
                    select(WebhookEvent).where(WebhookEvent.event_type == "ITEST_BadSig")
                )
            )
            .scalars()
            .first()
        )
        assert row is not None
        assert row.signature_valid is False
        assert row.status == "invalid_signature"


async def test_valid_event_stored_pending_and_idempotent(
    wh: tuple[httpx.AsyncClient, async_sessionmaker],
) -> None:
    ac, factory = wh
    body = json.dumps({"EventType": "ITEST_Valid", "Object": {"Id": 999000002}}).encode()
    sig = _sign(body)
    first = await ac.post(WEBHOOK_URL, content=body, headers={"Sign-Data": sig})
    duplicate = await ac.post(WEBHOOK_URL, content=body, headers={"Sign-Data": sig})
    assert first.status_code == 200
    assert duplicate.status_code == 200  # retry is a clean no-op
    async with factory() as session:
        rows = (
            (
                await session.execute(
                    select(WebhookEvent).where(WebhookEvent.event_type == "ITEST_Valid")
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1  # dedupe key collapsed the redelivery
        assert rows[0].status == "pending"
        assert rows[0].signature_valid is True
        assert rows[0].object_id == 999000002
