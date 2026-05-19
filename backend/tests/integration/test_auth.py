"""Auth tests for the v1 API.

Exercises the JWT-validation paths on `get_current_user`:
- missing Authorization header
- malformed bearer token
- valid signature but expired
- valid signature, wrong audience
- valid token (happy path)

Uses a no-DB-override client because none of these tests reach the DB —
auth runs first as a router-level dependency, so the endpoint handler
never executes when the token is invalid. Avoids the cross-event-loop
asyncpg pool issue without needing a dependency override here.
"""

from collections.abc import AsyncGenerator

import httpx
import pytest
from httpx import ASGITransport

from app.main import app
from tests.integration.conftest import mint_jwt


@pytest.fixture
async def unauth_client() -> AsyncGenerator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


async def test_missing_authorization_header_returns_401(
    unauth_client: httpx.AsyncClient,
) -> None:
    response = await unauth_client.get("/api/v1/work-orders/")
    assert response.status_code == 401


async def test_malformed_bearer_token_returns_401(
    unauth_client: httpx.AsyncClient,
) -> None:
    response = await unauth_client.get(
        "/api/v1/work-orders/",
        headers={"Authorization": "Bearer not-a-real-jwt"},
    )
    assert response.status_code == 401
    # Don't pin the exact wording — assert just that the 401 detail is
    # about the token (not e.g. a database error masquerading as a 401).
    assert "token" in response.json()["detail"].lower()


async def test_expired_token_returns_401(unauth_client: httpx.AsyncClient) -> None:
    expired = mint_jwt(expires_in_seconds=-60)  # issued in the past, already expired
    response = await unauth_client.get(
        "/api/v1/work-orders/",
        headers={"Authorization": f"Bearer {expired}"},
    )
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()


async def test_wrong_audience_returns_401(unauth_client: httpx.AsyncClient) -> None:
    """Supabase JWTs must have aud='authenticated'. A token signed with
    the right secret but a different audience must still be rejected."""
    token = mint_jwt(audience="some-other-service")
    response = await unauth_client.get(
        "/api/v1/work-orders/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


async def test_signature_mismatch_returns_401(unauth_client: httpx.AsyncClient) -> None:
    """A token signed with a different secret must be rejected even if
    everything else about its claims is well-formed."""
    forged = mint_jwt(secret="not-the-real-secret")
    response = await unauth_client.get(
        "/api/v1/work-orders/",
        headers={"Authorization": f"Bearer {forged}"},
    )
    assert response.status_code == 401


async def test_health_endpoint_is_unauthenticated(unauth_client: httpx.AsyncClient) -> None:
    """The top-level /health endpoint must remain reachable without a JWT
    so deployment health checks (Fly.io) work."""
    response = await unauth_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
