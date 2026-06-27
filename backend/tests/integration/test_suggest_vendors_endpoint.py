"""Integration test for GET /api/v1/work-orders/{id}/suggest-vendors.

Seeds one WO (known trade + an Austin location) and two vendors who both do the
trade — one in Austin, one in Longview — and asserts the in-area vendor is the
top pick. Uses a brand-new trade so no other dev vendors pass the trade gate,
isolating the result.
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
from app.models.work_order import Client, JobType, Location, Vendor, WorkOrder

# A made-up job type no real vendor carries, so the skill gate matches ONLY our
# two seeded vendors. The WO is categorized as this type (primary match path).
SC_BASE = 999007000
JOB_TYPE_NAME = "Zzqq Suggesttype"
NEAR_VENDOR = "ZZ SuggestTest Near"
FAR_VENDOR = "ZZ SuggestTest Far"

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
            # Deleting the vendors cascades their vendor_job_types rows.
            await s.execute(delete(Vendor).where(Vendor.name.in_([NEAR_VENDOR, FAR_VENDOR])))
            await s.execute(delete(JobType).where(JobType.name == JOB_TYPE_NAME))
            await s.execute(delete(Location).where(Location.sc_location_id == SC_BASE))
            await s.execute(delete(Client).where(Client.sc_subscriber_id == SC_BASE))
            await s.commit()

    async def _seed() -> None:
        async with factory() as s:
            c = Client(sc_subscriber_id=SC_BASE, name="Suggest Test Client")
            s.add(c)
            jt = JobType(name=JOB_TYPE_NAME, position=900, is_active=True)
            s.add(jt)
            await s.flush()
            loc = Location(
                sc_location_id=SC_BASE,
                client_id=c.id,
                name="Suggest Test Store",
                region="Austin",
                raw_data={"City": "Austin", "State": "TX"},
            )
            s.add(loc)
            near = Vendor(name=NEAR_VENDOR, is_active=True, service_area="Austin")
            far = Vendor(name=FAR_VENDOR, is_active=True, service_area="Longview only")
            near.job_types = [jt]
            far.job_types = [jt]
            s.add_all([near, far])
            await s.flush()
            wo = WorkOrder(
                sc_work_order_id=SC_BASE,
                sc_number=str(SC_BASE),
                primary_status="IN PROGRESS",
                brenk_category=JOB_TYPE_NAME,
                location_id=loc.id,
                client_id=c.id,
            )
            s.add(wo)
            await s.commit()
            _ids["wo"] = wo.id
            _ids["near"] = near.id
            _ids["far"] = far.id

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


async def test_suggest_vendors_ranks_in_area_first(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    resp = await client.get(
        f"/api/v1/work-orders/{_ids['wo']}/suggest-vendors", headers=auth_headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["has_trade"] is True
    assert body["wo_city"] == "Austin"

    # Both seeded vendors do the (brand-new) trade, so both are eligible and
    # nothing else in the DB is.
    ranked_ids = [s["vendor"]["id"] for s in body["ranked"]]
    assert set(ranked_ids) == {_ids["near"], _ids["far"]}

    # The Austin vendor is the top pick; the Longview vendor is out of area.
    assert body["top_pick"] is not None
    assert body["top_pick"]["vendor"]["id"] == _ids["near"]
    assert "covers Austin" in body["top_pick"]["reason"]
    assert body["top_pick"]["reason"].startswith("Does ")


async def test_suggest_vendors_deterministic(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    url = f"/api/v1/work-orders/{_ids['wo']}/suggest-vendors"
    first = (await client.get(url, headers=auth_headers)).json()
    second = (await client.get(url, headers=auth_headers)).json()
    assert first == second


async def test_suggest_vendors_404_on_missing_wo(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    resp = await client.get("/api/v1/work-orders/2000000999/suggest-vendors", headers=auth_headers)
    assert resp.status_code == 404, resp.text
