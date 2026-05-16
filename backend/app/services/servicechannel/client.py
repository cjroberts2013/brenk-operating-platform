"""ServiceChannel API client.

A thin, typed wrapper around the ServiceChannel v3 REST API. Handles:
- OAuth token management (delegated to ServiceChannelAuth)
- Retries with exponential backoff on transient failures
- Respect for Retry-After when throttled (429)
- Pagination for list endpoints

Reference: https://developer.servicechannel.com/swagger/ui/index?version=3
"""

import asyncio
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings
from app.core.exceptions import (
    ServiceChannelError,
    ServiceChannelNotFoundError,
    ServiceChannelThrottledError,
)
from app.services.servicechannel.auth import ServiceChannelAuth

logger = structlog.get_logger(__name__)

# Transient HTTP errors that justify a retry
_RETRYABLE_STATUS_CODES = {502, 503, 504}


class ServiceChannelClient:
    """High-level client for the ServiceChannel API."""

    def __init__(
        self,
        auth: ServiceChannelAuth | None = None,
        api_url: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        settings = get_settings()
        self.auth = auth or ServiceChannelAuth()
        self.api_url = api_url or settings.SC_API_URL
        self.timeout_seconds = timeout_seconds or settings.SC_REQUEST_TIMEOUT_SECONDS

    # -------------------------------------------------------------------------
    # Public methods
    # -------------------------------------------------------------------------

    async def list_work_orders(
        self,
        updated_since: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List work orders.

        Note: The exact filter parameter names are TBD pending API exploration.
        Update these once we confirm via Swagger.

        Args:
            updated_since: ISO 8601 timestamp to filter for WOs updated after this time.
            status: Optional status filter.
            limit: Number of records per request.
            offset: Pagination offset.

        Returns:
            A list of work order dicts as returned by the API.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if updated_since:
            params["updatedFrom"] = updated_since  # TODO: confirm exact param name
        if status:
            params["status"] = status

        response = await self._request("GET", "/v3/workorders", params=params)
        # The list endpoint returns a JSON array directly (confirmed empirically).
        return response if isinstance(response, list) else response.get("data", [])

    async def get_work_order(self, work_order_id: int | str) -> dict[str, Any]:
        """Fetch a single work order by its SC ID."""
        return await self._request("GET", f"/v3/workorders/{work_order_id}")

    async def get_work_order_notes(self, work_order_id: int | str) -> dict[str, Any]:
        """Fetch the full notes thread for a work order.

        Returns a dict with keys: Notes (list), AllNotesCount, UserNotesCount, SystemNotesCount.
        """
        return await self._request("GET", f"/v3/workorders/{work_order_id}/notes")

    async def get_work_order_attachments(self, work_order_id: int | str) -> list[dict[str, Any]]:
        """Fetch attachments for a work order.

        NOTE: The v3 endpoint returns UnsupportedApiVersion. The correct version is TBD —
        likely v2. Update this method once we confirm the right endpoint.
        """
        raise NotImplementedError(
            "Attachment endpoint version pending discovery — v3 returns UnsupportedApiVersion"
        )

    # -------------------------------------------------------------------------
    # Internal HTTP machinery
    # -------------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        retry=retry_if_exception_type((httpx.NetworkError, httpx.TimeoutException)),
        reraise=True,
    )
    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        """Make an authenticated request to the SC API with retry and throttle handling."""
        token = await self.auth.get_access_token()
        url = f"{self.api_url}{path}"

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.request(
                method,
                url,
                params=params,
                json=json,
                headers={"Authorization": f"Bearer {token}"},
            )

        if response.status_code == 401:
            logger.warning("SC returned 401 — invalidating cached token and retrying once")
            self.auth.invalidate()
            token = await self.auth.get_access_token()
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.request(
                    method,
                    url,
                    params=params,
                    json=json,
                    headers={"Authorization": f"Bearer {token}"},
                )

        if response.status_code == 429:
            retry_after = self._parse_retry_after(response.headers.get("Retry-After"))
            logger.warning(
                "SC throttled the request",
                method=method,
                path=path,
                retry_after_seconds=retry_after,
            )
            if retry_after and retry_after < 60:
                await asyncio.sleep(retry_after)
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.request(
                        method,
                        url,
                        params=params,
                        json=json,
                        headers={"Authorization": f"Bearer {token}"},
                    )
            else:
                raise ServiceChannelThrottledError(
                    f"SC throttled request to {path}",
                    retry_after_seconds=retry_after,
                )

        if response.status_code == 404:
            raise ServiceChannelNotFoundError(f"Not found: {method} {path}")

        if response.status_code in _RETRYABLE_STATUS_CODES:
            raise httpx.NetworkError(f"Transient SC error: {response.status_code}")

        if response.status_code >= 400:
            raise ServiceChannelError(
                f"SC API error: {response.status_code} {response.text}"
            )

        if not response.content:
            return None
        return response.json()

    @staticmethod
    def _parse_retry_after(value: str | None) -> float | None:
        """Parse a Retry-After header — supports both seconds and HTTP date format."""
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            pass
        try:
            target = parsedate_to_datetime(value)
            from datetime import UTC, datetime

            delta = (target - datetime.now(UTC)).total_seconds()
            return max(delta, 0)
        except (TypeError, ValueError):
            return None
