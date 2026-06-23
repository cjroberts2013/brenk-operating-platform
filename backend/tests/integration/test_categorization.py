"""Integration tests for WO categorization: batch task + PATCH confirm/override.

Seeds synthetic WOs (sc ids == SC_BASE+n, cleaned on teardown). The
single-WO Gemini call is monkeypatched — no real AI traffic.
"""

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
from app.models.work_order import Client, WorkOrder
from app.services import categorize as cat

SC_BASE = 999004000


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
            await session.execute(delete(WorkOrder).where(WorkOrder.sc_work_order_id >= SC_BASE))
            await session.execute(delete(Client).where(Client.sc_subscriber_id == SC_BASE))
            await session.commit()

    app.dependency_overrides[get_async_db] = _override
    await _cleanup()
    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", headers=auth_headers
        ) as ac:
            yield ac, factory
    finally:
        app.dependency_overrides.pop(get_async_db, None)
        await _cleanup()
        await engine.dispose()


async def _seed_wo(factory, client_id: int, n: int, *, description: str, category=None) -> int:
    async with factory() as s:
        wo = WorkOrder(
            sc_work_order_id=SC_BASE + n,
            sc_number=str(SC_BASE + n),
            primary_status="IN PROGRESS",
            description=description,
            client_id=client_id,
            brenk_category=category,
        )
        s.add(wo)
        await s.commit()
        return wo.id


async def _seed_client(factory) -> int:
    async with factory() as s:
        c = Client(sc_subscriber_id=SC_BASE, name="Cat Test Client")
        s.add(c)
        await s.commit()
        return c.id


# --------------------------------------------------------------------------- #
# Batch task
# --------------------------------------------------------------------------- #
async def test_batch_categorizes_only_uncategorized(harness, monkeypatch) -> None:
    _, factory = harness
    cid = await _seed_client(factory)
    uid1 = await _seed_wo(factory, cid, 1, description="X / Y / Outlet not working")
    uid2 = await _seed_wo(factory, cid, 2, description="X / Y / Roof is leaking")
    done = await _seed_wo(factory, cid, 3, description="X / Y / already done", category="Plumbing")

    async def fake_categorize(description, trade_hint=None):
        return ("Electrical", 0.9)

    monkeypatch.setattr(cat, "categorize", fake_categorize)
    # Ensure the batch function sees a key (it guards on it).
    monkeypatch.setattr(
        cat, "get_settings", lambda: get_settings().model_copy(update={"GEMINI_API_KEY": "k"})
    )

    # limit=2 = exactly our two NULL seeds. They sort to the very top
    # (sc ids ~999004xxx ≫ real WOs), so the batch never touches real dev
    # rows. The pre-categorized `done` WO is excluded by the IS NULL filter,
    # which is the skip-if-already-categorized (idempotency) guarantee.
    async with factory() as s:
        result = await cat.categorize_uncategorized(s, limit=2)

    assert result["categorized"] == 2

    async with factory() as s:
        rows = {
            r.id: r
            for r in (
                await s.execute(select(WorkOrder).where(WorkOrder.sc_work_order_id >= SC_BASE))
            ).scalars()
        }
    assert rows[uid1].brenk_category == "Electrical"
    assert rows[uid1].brenk_category_source == "ai"
    assert rows[uid1].brenk_category_ai == "Electrical"
    assert rows[uid2].brenk_category == "Electrical"
    assert rows[done].brenk_category == "Plumbing"  # untouched (was already set)


async def test_batch_respects_limit(harness, monkeypatch) -> None:
    _, factory = harness
    cid = await _seed_client(factory)
    for n in range(1, 6):
        await _seed_wo(factory, cid, n, description=f"X / Y / problem {n}")

    async def fake_categorize(description, trade_hint=None):
        return ("Other", 0.5)

    monkeypatch.setattr(cat, "categorize", fake_categorize)
    monkeypatch.setattr(
        cat, "get_settings", lambda: get_settings().model_copy(update={"GEMINI_API_KEY": "k"})
    )

    async with factory() as s:
        result = await cat.categorize_uncategorized(s, limit=2)
    assert result["categorized"] == 2  # capped


# --------------------------------------------------------------------------- #
# PATCH confirm / override
# --------------------------------------------------------------------------- #
async def test_patch_confirm_marks_confirmed(harness) -> None:
    ac, factory = harness
    cid = await _seed_client(factory)
    wo_id = await _seed_wo(factory, cid, 10, description="X / Y / breaker", category="Electrical")
    # Pretend the AI set it.
    async with factory() as s:
        wo = (await s.execute(select(WorkOrder).where(WorkOrder.id == wo_id))).scalar_one()
        wo.brenk_category_source = "ai"
        await s.commit()

    resp = await ac.patch(f"/api/v1/work-orders/{wo_id}", json={"category_action": "confirm"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["brenk_category"] == "Electrical"
    assert body["brenk_category_source"] == "confirmed"


async def test_patch_override_sets_manual(harness) -> None:
    ac, factory = harness
    cid = await _seed_client(factory)
    wo_id = await _seed_wo(factory, cid, 11, description="X / Y / door", category="Electrical")

    resp = await ac.patch(f"/api/v1/work-orders/{wo_id}", json={"brenk_category": "Doors"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["brenk_category"] == "Doors"
    assert body["brenk_category_source"] == "manual"


async def test_patch_rejects_unknown_category(harness) -> None:
    ac, factory = harness
    cid = await _seed_client(factory)
    wo_id = await _seed_wo(factory, cid, 12, description="X / Y / thing")
    resp = await ac.patch(f"/api/v1/work-orders/{wo_id}", json={"brenk_category": "Bogus"})
    assert resp.status_code == 400
    assert "category" in resp.json()["detail"].lower()


async def test_categories_endpoint_lists_taxonomy(harness) -> None:
    ac, _ = harness
    resp = await ac.get("/api/v1/categories/")
    assert resp.status_code == 200
    cats = resp.json()["categories"]
    assert "Electrical" in cats and "Other" in cats
