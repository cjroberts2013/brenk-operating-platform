"""Integration tests for multi-vendor assignment endpoints + primary resync."""

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
from app.models.work_order import Client, JobType, Vendor, WorkOrder

SC_BASE = 999009000
V1 = "ZZ Assign V1"
V2 = "ZZ Assign V2"
_ids: dict[str, int] = {}


@pytest.fixture
async def client() -> AsyncGenerator[httpx.AsyncClient]:
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL_ASYNC, poolclass=NullPool)
    factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )

    async def _override() -> AsyncGenerator[AsyncSession]:
        async with factory() as session:
            yield session

    async def _cleanup() -> None:
        async with factory() as s:
            await s.execute(delete(WorkOrder).where(WorkOrder.sc_work_order_id == SC_BASE))
            await s.execute(delete(Vendor).where(Vendor.name.in_([V1, V2])))
            await s.execute(delete(Client).where(Client.sc_subscriber_id == SC_BASE))
            await s.commit()

    async def _seed() -> None:
        async with factory() as s:
            c = Client(sc_subscriber_id=SC_BASE, name="Assign Test Client")
            s.add(c)
            v1 = Vendor(name=V1, is_active=True)
            v2 = Vendor(name=V2, is_active=True)
            s.add_all([v1, v2])
            await s.flush()
            wo = WorkOrder(
                sc_work_order_id=SC_BASE,
                sc_number=str(SC_BASE),
                primary_status="IN PROGRESS",
                client_id=c.id,
            )
            s.add(wo)
            await s.commit()
            _ids["wo"] = wo.id
            _ids["v1"] = v1.id
            _ids["v2"] = v2.id
            jt = (await s.execute(select(JobType).limit(1))).scalar_one()
            _ids["jt"] = jt.id

    app.dependency_overrides[get_async_db] = _override
    await _cleanup()
    await _seed()
    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_async_db, None)
        await _cleanup()
        await engine.dispose()


async def test_add_remove_and_primary_resync(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    wo = _ids["wo"]
    base = f"/api/v1/work-orders/{wo}/assignments"

    # Add v1 -> one assignment, v1 is primary.
    r = await client.post(base, headers=auth_headers, json={"vendor_id": _ids["v1"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert [a["vendor"]["id"] for a in body["vendor_assignments"]] == [_ids["v1"]]
    assert body["assigned_vendor"]["id"] == _ids["v1"]

    # Add v2 with a job type -> two assignments, v1 still primary.
    r = await client.post(
        base, headers=auth_headers, json={"vendor_id": _ids["v2"], "job_type_id": _ids["jt"]}
    )
    body = r.json()
    assert {a["vendor"]["id"] for a in body["vendor_assignments"]} == {_ids["v1"], _ids["v2"]}
    assert body["assigned_vendor"]["id"] == _ids["v1"]
    v2_row = next(a for a in body["vendor_assignments"] if a["vendor"]["id"] == _ids["v2"])
    assert v2_row["job_type"]["id"] == _ids["jt"]

    # Adding v1 again is idempotent.
    r = await client.post(base, headers=auth_headers, json={"vendor_id": _ids["v1"]})
    assert len(r.json()["vendor_assignments"]) == 2

    # Per-vendor notify on v2.
    r = await client.patch(f"{base}/{_ids['v2']}", headers=auth_headers, json={"notified": "now"})
    body = r.json()
    v2_row = next(a for a in body["vendor_assignments"] if a["vendor"]["id"] == _ids["v2"])
    assert v2_row["notified_at"] is not None
    # v1 (primary) wasn't notified, so the legacy WO-level field stays null.
    assert body["brenk_vendor_notified_at"] is None

    # Remove v1 -> v2 becomes primary.
    r = await client.delete(f"{base}/{_ids['v1']}", headers=auth_headers)
    body = r.json()
    assert [a["vendor"]["id"] for a in body["vendor_assignments"]] == [_ids["v2"]]
    assert body["assigned_vendor"]["id"] == _ids["v2"]
    # v2 was notified and is now primary -> legacy field mirrors it.
    assert body["brenk_vendor_notified_at"] is not None

    # Remove v2 -> unassigned.
    r = await client.delete(f"{base}/{_ids['v2']}", headers=auth_headers)
    body = r.json()
    assert body["vendor_assignments"] == []
    assert body["assigned_vendor"] is None


async def test_patch_assigned_vendor_replaces_set(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    wo = _ids["wo"]
    base = f"/api/v1/work-orders/{wo}/assignments"
    await client.post(base, headers=auth_headers, json={"vendor_id": _ids["v1"]})
    await client.post(base, headers=auth_headers, json={"vendor_id": _ids["v2"]})

    # Legacy single-vendor PATCH makes v2 the sole assignment.
    r = await client.patch(
        f"/api/v1/work-orders/{wo}", headers=auth_headers, json={"assigned_vendor_id": _ids["v2"]}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert [a["vendor"]["id"] for a in body["vendor_assignments"]] == [_ids["v2"]]


async def test_pricing_rollup_paid_and_payables(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    from decimal import Decimal

    wo = _ids["wo"]
    base = f"/api/v1/work-orders/{wo}/assignments"
    await client.post(base, headers=auth_headers, json={"vendor_id": _ids["v1"]})
    await client.post(base, headers=auth_headers, json={"vendor_id": _ids["v2"]})

    # Per-vendor payouts + a WO-level markup, in one atomic pricing call.
    r = await client.put(
        f"/api/v1/work-orders/{wo}/pricing",
        headers=auth_headers,
        json={
            "costs": [
                {"vendor_id": _ids["v1"], "labor_cost": "100", "material_cost": "20"},
                {"vendor_id": _ids["v2"], "labor_cost": "50", "material_cost": "0"},
            ],
            "brenk_markup_percent": "50",
            "set_markup": True,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # WO-level rollup = sum of payouts: labor 100+50=150, material 20+0=20.
    assert Decimal(body["brenk_labor_cost"]) == Decimal("150")
    assert Decimal(body["brenk_material_cost"]) == Decimal("20")
    assert Decimal(body["brenk_markup_percent"]) == Decimal("50")
    v1_row = next(a for a in body["vendor_assignments"] if a["vendor"]["id"] == _ids["v1"])
    assert Decimal(v1_row["labor_cost"]) == Decimal("100")

    # Pay v1 -> v1 drops out of payables, v2 (owed 50) stays.
    r = await client.patch(f"{base}/{_ids['v1']}", headers=auth_headers, json={"paid": "now"})
    v1_row = next(a for a in r.json()["vendor_assignments"] if a["vendor"]["id"] == _ids["v1"])
    assert v1_row["paid_to_vendor_at"] is not None

    r = await client.get("/api/v1/reports/payables", headers=auth_headers)
    assert r.status_code == 200, r.text
    owed = {i["vendor_id"]: i for i in r.json()["items"]}
    assert _ids["v1"] not in owed
    assert _ids["v2"] in owed
    assert Decimal(owed[_ids["v2"]]["payout"]) == Decimal("50")


async def test_bad_vendor_and_missing(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    wo = _ids["wo"]
    r = await client.post(
        f"/api/v1/work-orders/{wo}/assignments", headers=auth_headers, json={"vendor_id": 999999}
    )
    assert r.status_code == 400
    r = await client.post(
        "/api/v1/work-orders/2000000999/assignments", headers=auth_headers, json={"vendor_id": _ids["v1"]}
    )
    assert r.status_code == 404
