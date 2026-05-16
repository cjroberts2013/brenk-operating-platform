"""Tests for the ServiceChannel API client — pagination behavior.

Hits no real SC endpoints; mocks the HTTP layer with respx and stubs out the
auth dependency.
"""

from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from app.services.servicechannel.auth import ServiceChannelAuth
from app.services.servicechannel.client import ServiceChannelClient


def _fake_record(wo_id: int) -> dict[str, Any]:
    """Minimal SC work-order-shaped dict for pagination tests."""
    return {"Id": wo_id, "Number": str(wo_id), "Status": {"Primary": "OPEN"}}


@pytest.fixture
def client() -> ServiceChannelClient:
    """Client wired to a fake API URL with a stubbed auth token."""
    auth = ServiceChannelAuth(
        login_url="https://login.example.com",
        client_id="cid",
        client_secret="cs",
        username="u",
        password="p",
    )
    auth.get_access_token = AsyncMock(return_value="fake-token")  # type: ignore[method-assign]
    return ServiceChannelClient(auth=auth, api_url="https://api.example.com")


@pytest.mark.asyncio
async def test_iter_work_orders_paginates_until_partial(
    client: ServiceChannelClient,
) -> None:
    """Three pages: 50, 50, 25 records. Iterator yields all 125 and stops."""
    page_records = {
        1: [_fake_record(i) for i in range(1, 51)],
        2: [_fake_record(i) for i in range(51, 101)],
        3: [_fake_record(i) for i in range(101, 126)],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params.get("page", "1"))
        return httpx.Response(200, json=page_records.get(page, []))

    with respx.mock:
        route = respx.get("https://api.example.com/v3/workorders").mock(side_effect=handler)

        seen = [wo async for wo in client.iter_work_orders()]

    assert [r["Id"] for r in seen] == list(range(1, 126))
    assert route.call_count == 3  # stopped after partial page, not 4


@pytest.mark.asyncio
async def test_iter_work_orders_stops_on_empty_first_page(
    client: ServiceChannelClient,
) -> None:
    """An empty first page short-circuits the loop."""
    with respx.mock:
        route = respx.get("https://api.example.com/v3/workorders").mock(
            return_value=httpx.Response(200, json=[])
        )

        seen = [wo async for wo in client.iter_work_orders()]

    assert seen == []
    assert route.call_count == 1


@pytest.mark.asyncio
async def test_iter_work_orders_respects_max_pages(
    client: ServiceChannelClient,
) -> None:
    """If SC keeps returning full pages, the safety cap halts iteration."""
    full_page = [_fake_record(i) for i in range(50)]
    with respx.mock:
        route = respx.get("https://api.example.com/v3/workorders").mock(
            return_value=httpx.Response(200, json=full_page)
        )

        seen = [wo async for wo in client.iter_work_orders(max_pages=3)]

    assert len(seen) == 150  # 3 pages of 50
    assert route.call_count == 3


@pytest.mark.asyncio
async def test_list_work_orders_page_clamps_oversize_page_size(
    client: ServiceChannelClient,
) -> None:
    """Requesting pageSize > 50 sends pageSize=50 in the query string."""
    with respx.mock:
        route = respx.get("https://api.example.com/v3/workorders").mock(
            return_value=httpx.Response(200, json=[])
        )

        await client.list_work_orders_page(page=1, page_size=500)

    assert route.call_count == 1
    sent_params = dict(route.calls[0].request.url.params)
    assert sent_params["pageSize"] == "50"
    assert sent_params["page"] == "1"
