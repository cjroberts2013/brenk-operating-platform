"""Integration tests for the turnaround-deadline filter + digest query.

Creates synthetic work orders (ids >= 999002000) at various points
around the deadline and asserts the `?deadline=` filter, the per-row
deadline fields, the dashboard's deadline_watch counts, and the digest
item query all agree. Cleans up on teardown.
"""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.db.session import get_async_db
from app.main import app
from app.models.work_order import WorkOrder
from app.services.deadline_digest import fetch_digest_items

BASE = 999002000

_NOW = datetime.now(UTC)

# name -> WO kwargs describing where the WO sits relative to its deadline
CASES = {
    # scheduled 12 days ago, work unfinished -> overdue, Daryl's move
    "overdue": dict(
        primary_status="IN PROGRESS",
        extended_status="DISPATCH CONFIRMED",
        scheduled_date=_NOW - timedelta(days=12),
    ),
    # due tomorrow -> due_soon
    "due_soon": dict(
        primary_status="IN PROGRESS",
        extended_status="WAITING FOR QUOTE",
        scheduled_date=_NOW + timedelta(days=1),
    ),
    # comfortably inside turnaround -> not at risk
    "ok": dict(
        primary_status="IN PROGRESS",
        extended_status="DISPATCH CONFIRMED",
        scheduled_date=_NOW + timedelta(days=10),
    ),
    # no scheduled_date: falls back to call_date + 5d = 5 days ago -> overdue
    "fallback": dict(
        primary_status="IN PROGRESS",
        extended_status="DISPATCH CONFIRMED",
        scheduled_date=None,
        call_date=_NOW - timedelta(days=10),
    ),
    # work already complete -> turnaround met, never at risk
    "completed": dict(
        primary_status="COMPLETED",
        extended_status="CONFIRMED",
        scheduled_date=_NOW - timedelta(days=12),
    ),
    # overdue but blocked on CubeSmart -> waiting_on_cubesmart section
    "waiting": dict(
        primary_status="IN PROGRESS",
        extended_status="WAITING FOR APPROVAL",
        scheduled_date=_NOW - timedelta(days=3),
    ),
    # no dates at all -> no deadline, excluded
    "no_dates": dict(
        primary_status="IN PROGRESS",
        extended_status="DISPATCH CONFIRMED",
        scheduled_date=None,
        call_date=None,
    ),
}


@pytest.fixture
async def env(
    auth_headers: dict[str, str],
) -> AsyncGenerator[tuple[httpx.AsyncClient, dict[str, str], async_sessionmaker[AsyncSession]]]:
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL_ASYNC, poolclass=NullPool)
    factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )
    numbers: dict[str, str] = {}
    async with factory() as s:
        for i, (name, kwargs) in enumerate(CASES.items()):
            woid = BASE + i
            num = f"DDLN{woid}"
            numbers[name] = num
            s.add(WorkOrder(sc_work_order_id=woid, sc_number=num, **kwargs))
        await s.commit()

    async def _override() -> AsyncGenerator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_async_db] = _override
    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", headers=auth_headers
        ) as ac:
            yield ac, numbers, factory
    finally:
        app.dependency_overrides.pop(get_async_db, None)
        async with factory() as s:
            await s.execute(delete(WorkOrder).where(WorkOrder.sc_work_order_id >= BASE))
            await s.commit()
        await engine.dispose()


async def _filtered(client: httpx.AsyncClient, key: str) -> dict[str, dict]:
    r = await client.get("/api/v1/work-orders/", params={"deadline": key, "page_size": 200})
    assert r.status_code == 200, r.text
    return {it["sc_number"]: it for it in r.json()["items"]}


async def test_deadline_filter_buckets(env) -> None:
    client, num, _ = env
    overdue = await _filtered(client, "overdue")
    due_soon = await _filtered(client, "due_soon")
    at_risk = await _filtered(client, "at_risk")

    expected_overdue = {num["overdue"], num["fallback"], num["waiting"]}
    expected_due_soon = {num["due_soon"]}
    never = {num["ok"], num["completed"], num["no_dates"]}

    assert expected_overdue <= set(overdue)
    assert expected_due_soon <= set(due_soon)
    assert (expected_overdue | expected_due_soon) <= set(at_risk)

    for n in never:
        assert n not in at_risk, f"{n} should never be at risk"
    for n in expected_due_soon:
        assert n not in overdue
    for n in expected_overdue:
        assert n not in due_soon


async def test_rows_carry_computed_deadline_fields(env) -> None:
    client, num, _ = env
    at_risk = await _filtered(client, "at_risk")

    row = at_risk[num["overdue"]]
    assert row["deadline_urgency"] == "overdue"
    assert row["deadline_days_past"] > 11
    assert row["deadline_date"] is not None

    row = at_risk[num["due_soon"]]
    assert row["deadline_urgency"] == "due_soon"
    assert row["deadline_days_past"] < 0

    # A completed WO carries no deadline fields (clock stopped).
    r = await client.get("/api/v1/work-orders/", params={"q": num["completed"]})
    row = next(it for it in r.json()["items"] if it["sc_number"] == num["completed"])
    assert row["deadline_urgency"] is None
    assert row["deadline_date"] is None


async def test_invalid_deadline_key_is_422(env) -> None:
    client, _, _ = env
    r = await client.get("/api/v1/work-orders/", params={"deadline": "bogus"})
    assert r.status_code == 422


async def test_dashboard_counts_match_list_totals(env) -> None:
    """The Deadline watch panel counts must equal the row totals of the
    lists its links land on — same clauses by construction, verified."""
    client, _, _ = env
    dash = await client.get("/api/v1/dashboard/pipeline")
    assert dash.status_code == 200, dash.text
    watch = dash.json()["deadline_watch"]

    for key, count_field in (("overdue", "overdue_count"), ("due_soon", "due_soon_count")):
        r = await client.get("/api/v1/work-orders/", params={"deadline": key, "page_size": 1})
        assert watch[count_field] == r.json()["total"], key

    assert (
        watch["needs_action_count"] + watch["waiting_on_cubesmart_count"]
        == watch["overdue_count"] + watch["due_soon_count"]
    )


async def test_digest_items_sections_and_urls(env) -> None:
    _, num, factory = env
    async with factory() as session:
        items = {i.sc_number: i for i in await fetch_digest_items(session)}

    assert items[num["overdue"]].section == "needs_action"
    assert items[num["waiting"]].section == "waiting_on_cubesmart"
    assert items[num["due_soon"]].urgency == "due_soon"
    assert num["completed"] not in items
    assert num["ok"] not in items

    item = items[num["overdue"]]
    assert "/work-orders/" in item.dashboard_url
    assert item.dashboard_url.rsplit("/", 1)[-1].isdigit()  # internal id, not sc_number
    assert item.sc_url.endswith(f"/sc/wo/Workorders/index?id={BASE}")
