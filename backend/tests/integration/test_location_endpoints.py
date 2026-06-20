"""Integration tests for /api/v1/locations and the sync-preservation rule.

Locations are SC-sourced (no POST-create), so each test seeds its own
client + location (+ optional work orders / gate codes) directly through a
NullPool session and tears them down in a fixture finalizer, mirroring the
self-cleaning style of test_vendor_endpoints.

The critical test here is `test_sync_preserves_brenk_fields`: it proves the
work-order sync can never clobber operator-entered enrichment.
"""

from collections.abc import AsyncGenerator, Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.db.session import get_async_db
from app.main import app
from app.models.work_order import Client, GateCode, Location, WorkOrder
from app.services.sync.upserter import upsert_location


@pytest.fixture
async def client(auth_headers: dict[str, str]) -> AsyncGenerator[httpx.AsyncClient]:
    settings = get_settings()
    test_engine = create_async_engine(settings.DATABASE_URL_ASYNC, poolclass=NullPool)
    session_factory = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
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


SeedFn = Callable[..., Awaitable[dict[str, Any]]]


@pytest.fixture
async def seed() -> AsyncGenerator[SeedFn]:
    """Factory that creates a client + location (+ optional WOs / gate codes)
    and cleans them all up afterward. SC ids are taken above the current max
    so they never collide with real synced data or leftover rows."""
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL_ASYNC, poolclass=NullPool)
    factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )
    location_ids: list[int] = []
    client_ids: list[int] = []

    # Seed SC ids above the current max across the three tables so inserts
    # never collide on the unique sc_* columns.
    async with factory() as s:
        base = 0
        for tbl, col in (
            ("locations", "sc_location_id"),
            ("clients", "sc_subscriber_id"),
            ("work_orders", "sc_work_order_id"),
        ):
            mx = (await s.execute(text(f"SELECT COALESCE(MAX({col}), 0) FROM {tbl}"))).scalar() or 0
            base = max(base, int(mx))
    counter = {"n": base + 1000}

    def _uniq() -> int:
        counter["n"] += 1
        return counter["n"]

    async def _make(
        *,
        wo_statuses: tuple[str, ...] = (),
        gate_codes: tuple[tuple[str, str | None], ...] = (),
        **loc_fields: Any,
    ) -> dict[str, Any]:
        async with factory() as s:
            cl = Client(sc_subscriber_id=_uniq(), name="SC Test Client")
            s.add(cl)
            await s.flush()
            loc = Location(sc_location_id=_uniq(), client_id=cl.id, **loc_fields)
            s.add(loc)
            await s.flush()
            for status in wo_statuses:
                woid = _uniq()
                s.add(
                    WorkOrder(
                        sc_work_order_id=woid,
                        sc_number=str(woid),
                        primary_status=status,
                        location_id=loc.id,
                        client_id=cl.id,
                        sc_updated_date=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
                    )
                )
            for code, label in gate_codes:
                s.add(GateCode(location_id=loc.id, code=code, label=label, is_active=True))
            await s.commit()
            location_ids.append(loc.id)
            client_ids.append(cl.id)
            return {
                "location_id": loc.id,
                "client_id": cl.id,
                "sc_location_id": loc.sc_location_id,
            }

    try:
        yield _make
    finally:
        async with factory() as s:
            for lid in location_ids:
                await s.execute(text("DELETE FROM gate_codes WHERE location_id = :i"), {"i": lid})
                await s.execute(text("DELETE FROM work_orders WHERE location_id = :i"), {"i": lid})
                await s.execute(text("DELETE FROM locations WHERE id = :i"), {"i": lid})
            for cid in client_ids:
                await s.execute(text("DELETE FROM clients WHERE id = :i"), {"i": cid})
            await s.commit()
        await engine.dispose()


# -----------------------------------------------------------------------------
# List + detail
# -----------------------------------------------------------------------------


async def test_list_shape_and_finds_seeded(client: httpx.AsyncClient, seed: SeedFn) -> None:
    info = await seed(store_id="ZZZ-LIST", name="Sentinel List Location")
    response = await client.get("/api/v1/locations/", params={"q": "ZZZ-LIST", "page_size": 50})
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size"}
    ids = {item["id"] for item in body["items"]}
    assert info["location_id"] in ids


async def test_list_filter_by_rating(client: httpx.AsyncClient, seed: SeedFn) -> None:
    problem = await seed(store_id="ZZZ-PROB", rating="problem")
    good = await seed(store_id="ZZZ-GOOD", rating="good")
    response = await client.get(
        "/api/v1/locations/", params={"rating": "problem", "page_size": 200}
    )
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert problem["location_id"] in ids
    assert good["location_id"] not in ids


async def test_detail_returns_related_wos_and_metrics(
    client: httpx.AsyncClient, seed: SeedFn
) -> None:
    info = await seed(
        store_id="ZZZ-DET",
        name="Detail Location",
        wo_statuses=("OPEN", "IN PROGRESS", "COMPLETED"),
    )
    response = await client.get(f"/api/v1/locations/{info['location_id']}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["store_id"] == "ZZZ-DET"
    assert body["total_work_orders"] == 3
    assert body["active_work_orders"] == 2  # COMPLETED is terminal
    assert body["last_work_order_date"] is not None
    # Work orders are paginated via a separate endpoint, not embedded.
    assert "work_orders" not in body
    assert body["gate_codes_active"] == []
    assert body["gate_codes_history"] == []


async def test_work_orders_endpoint_paginates(
    client: httpx.AsyncClient, seed: SeedFn
) -> None:
    info = await seed(
        store_id="ZZZ-WOS",
        wo_statuses=("OPEN", "IN PROGRESS", "COMPLETED", "OPEN", "OPEN"),
    )
    loc_id = info["location_id"]

    first = await client.get(
        f"/api/v1/locations/{loc_id}/work-orders", params={"page": 1, "page_size": 2}
    )
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["total"] == 5  # uncapped count
    assert body["page"] == 1
    assert len(body["items"]) == 2

    third = await client.get(
        f"/api/v1/locations/{loc_id}/work-orders", params={"page": 3, "page_size": 2}
    )
    assert third.status_code == 200
    assert len(third.json()["items"]) == 1  # 5 total → page 3 has the remainder


async def test_work_orders_endpoint_404_for_unknown_location(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/api/v1/locations/999999999/work-orders")
    assert response.status_code == 404


async def test_detail_404(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/locations/999999999")
    assert response.status_code == 404


# -----------------------------------------------------------------------------
# PATCH enrichment
# -----------------------------------------------------------------------------


async def test_patch_updates_only_sent_fields(client: httpx.AsyncClient, seed: SeedFn) -> None:
    info = await seed(rating="watch", description="initial context")
    response = await client.patch(
        f"/api/v1/locations/{info['location_id']}",
        json={"district_manager_name": "Dana Manager", "rating": "problem"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["district_manager_name"] == "Dana Manager"
    assert body["rating"] == "problem"
    assert body["description"] == "initial context"  # untouched


async def test_patch_rejects_invalid_rating(client: httpx.AsyncClient, seed: SeedFn) -> None:
    info = await seed()
    response = await client.patch(
        f"/api/v1/locations/{info['location_id']}",
        json={"rating": "terrible"},
    )
    assert response.status_code == 422


async def test_patch_404(client: httpx.AsyncClient) -> None:
    response = await client.patch("/api/v1/locations/999999999", json={"rating": "good"})
    assert response.status_code == 404


# -----------------------------------------------------------------------------
# Gate codes
# -----------------------------------------------------------------------------


async def test_gate_code_add_multiple_active_then_invalidate(
    client: httpx.AsyncClient, seed: SeedFn
) -> None:
    info = await seed()
    loc_id = info["location_id"]

    first = await client.post(
        f"/api/v1/locations/{loc_id}/gate-codes",
        json={"code": "1234#", "label": "front gate"},
    )
    assert first.status_code == 201, first.text
    assert first.json()["is_active"] is True
    assert first.json()["invalidated_at"] is None

    second = await client.post(
        f"/api/v1/locations/{loc_id}/gate-codes",
        json={"code": "9999", "label": "loading dock"},
    )
    assert second.status_code == 201
    first_id = first.json()["id"]

    # Both active simultaneously.
    detail = (await client.get(f"/api/v1/locations/{loc_id}")).json()
    assert len(detail["gate_codes_active"]) == 2
    assert detail["gate_codes_history"] == []

    # Invalidate the first.
    inv = await client.post(f"/api/v1/locations/{loc_id}/gate-codes/{first_id}/invalidate")
    assert inv.status_code == 200, inv.text
    assert inv.json()["is_active"] is False
    assert inv.json()["invalidated_at"] is not None

    # It moves to history; the other stays active.
    detail = (await client.get(f"/api/v1/locations/{loc_id}")).json()
    active_ids = {gc["id"] for gc in detail["gate_codes_active"]}
    history_ids = {gc["id"] for gc in detail["gate_codes_history"]}
    assert first_id in history_ids
    assert first_id not in active_ids
    assert len(detail["gate_codes_active"]) == 1

    # Invalidating again is idempotent.
    again = await client.post(f"/api/v1/locations/{loc_id}/gate-codes/{first_id}/invalidate")
    assert again.status_code == 200
    assert again.json()["is_active"] is False


async def test_gate_code_invalidate_wrong_location_404(
    client: httpx.AsyncClient, seed: SeedFn
) -> None:
    owner = await seed(gate_codes=(("4321", None),))
    other = await seed()
    # Find the owner's gate-code id via its detail.
    detail = (await client.get(f"/api/v1/locations/{owner['location_id']}")).json()
    code_id = detail["gate_codes_active"][0]["id"]
    # Invalidating it under a different location must 404.
    response = await client.post(
        f"/api/v1/locations/{other['location_id']}/gate-codes/{code_id}/invalidate"
    )
    assert response.status_code == 404


async def test_gate_code_add_to_unknown_location_404(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/v1/locations/999999999/gate-codes", json={"code": "0000"})
    assert response.status_code == 404


async def test_gate_code_invalidate_unknown_code_404(
    client: httpx.AsyncClient, seed: SeedFn
) -> None:
    info = await seed()
    response = await client.post(
        f"/api/v1/locations/{info['location_id']}/gate-codes/999999999/invalidate"
    )
    assert response.status_code == 404


# -----------------------------------------------------------------------------
# CRITICAL: sync must never clobber Brenk enrichment
# -----------------------------------------------------------------------------


async def test_sync_preserves_brenk_fields(seed: SeedFn) -> None:
    """Set enrichment + a gate code, then re-run upsert_location with a
    changed SC payload. SC fields update; Brenk fields + gate codes survive."""
    info = await seed(
        store_id="OLD-STORE",
        name="Old Name",
        rating="problem",
        description="watch this site",
        district_manager_name="Pat DM",
        district_manager_phone="+15555550123",
        gate_codes=(("1111", "front"),),
    )

    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL_ASYNC, poolclass=NullPool)
    factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )
    try:
        async with factory() as s:
            # An SC payload for the same location with changed SC fields.
            payload = {
                "Id": info["sc_location_id"],
                "StoreId": "NEW-STORE",
                "Name": "New Name",
                "IsInternational": False,
            }
            loc = await upsert_location(s, payload, info["client_id"])
            await s.commit()

            # SC fields updated...
            assert loc.store_id == "NEW-STORE"
            assert loc.name == "New Name"
            # ...Brenk enrichment preserved.
            assert loc.rating == "problem"
            assert loc.description == "watch this site"
            assert loc.district_manager_name == "Pat DM"
            assert loc.district_manager_phone == "+15555550123"

            # Gate codes untouched.
            codes = (
                (
                    await s.execute(
                        select(GateCode).where(GateCode.location_id == info["location_id"])
                    )
                )
                .scalars()
                .all()
            )
            assert len(codes) == 1
            assert codes[0].code == "1111"
            assert codes[0].is_active is True
    finally:
        await engine.dispose()
