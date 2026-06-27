"""Integration tests for the job-types management endpoints, including the
rename cascade onto work_orders.brenk_category."""

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
from app.models.work_order import Client, JobType, WorkOrder

SC_BASE = 999008000
SEED_NAME = "Zzqq Testtype"
RENAMED = "Zzqq Renamedtype"

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
            await s.execute(delete(Client).where(Client.sc_subscriber_id == SC_BASE))
            await s.execute(delete(JobType).where(JobType.name.in_([SEED_NAME, RENAMED])))
            await s.commit()

    async def _seed() -> None:
        async with factory() as s:
            jt = JobType(name=SEED_NAME, description="seed", position=900, is_active=True)
            s.add(jt)
            c = Client(sc_subscriber_id=SC_BASE, name="JT Test Client")
            s.add(c)
            await s.flush()
            # A WO already categorized as the seed type, to prove the rename cascade.
            s.add(
                WorkOrder(
                    sc_work_order_id=SC_BASE,
                    sc_number=str(SC_BASE),
                    primary_status="IN PROGRESS",
                    brenk_category=SEED_NAME,
                    client_id=c.id,
                )
            )
            await s.commit()
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


async def test_rename_cascades_to_work_orders(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    resp = await client.patch(
        f"/api/v1/job-types/{_ids['jt']}",
        headers=auth_headers,
        json={"name": RENAMED},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == RENAMED

    # The WO that was categorized under the old name now reads the new name.
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL_ASYNC, poolclass=NullPool)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        cat = (
            await s.execute(
                select(WorkOrder.brenk_category).where(WorkOrder.sc_work_order_id == SC_BASE)
            )
        ).scalar_one()
    await engine.dispose()
    assert cat == RENAMED


async def test_duplicate_name_conflicts(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    # "Electrical" is seeded by the migration — creating it again is a 409.
    resp = await client.post(
        "/api/v1/job-types/", headers=auth_headers, json={"name": "Electrical"}
    )
    assert resp.status_code == 409, resp.text


async def test_list_includes_seed_and_catchall(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    resp = await client.get("/api/v1/job-types/", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    names = [r["name"] for r in resp.json()]
    assert SEED_NAME in names
    assert "Other" in names
