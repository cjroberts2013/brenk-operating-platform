"""Smoke tests for ServiceChannelAuth — token caching and expiration logic.

These tests do not call the real SC API; they mock the HTTP layer with respx.
"""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from app.services.servicechannel.auth import ServiceChannelAuth


@pytest.fixture
def auth() -> ServiceChannelAuth:
    return ServiceChannelAuth(
        login_url="https://sb2login.example.com",
        client_id="test_client_id",
        client_secret="test_client_secret",
        username="test_user",
        password="test_pass",
    )


@pytest.mark.asyncio
async def test_request_new_token_succeeds(auth: ServiceChannelAuth) -> None:
    """A successful password grant stores the token and expiry."""
    with respx.mock:
        respx.post("https://sb2login.example.com/oauth/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "fake_access_token",
                    "refresh_token": "fake_refresh_token",
                    "expires_in": 600,
                    "token_type": "bearer",
                },
            )
        )

        token = await auth.get_access_token()
        assert token == "fake_access_token"
        assert auth._refresh_token == "fake_refresh_token"
        assert auth._expires_at is not None
        assert auth._expires_at > datetime.now(UTC)


@pytest.mark.asyncio
async def test_cached_token_is_reused(auth: ServiceChannelAuth) -> None:
    """Calling get_access_token twice while the token is fresh hits the network once."""
    with respx.mock:
        route = respx.post("https://sb2login.example.com/oauth/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "fake_access_token",
                    "refresh_token": "fake_refresh_token",
                    "expires_in": 600,
                    "token_type": "bearer",
                },
            )
        )

        await auth.get_access_token()
        await auth.get_access_token()

        assert route.call_count == 1


@pytest.mark.asyncio
async def test_expired_token_triggers_refresh(auth: ServiceChannelAuth) -> None:
    """When a token is near expiry, the refresh path is taken."""
    auth._access_token = "old_token"
    auth._refresh_token = "old_refresh"
    auth._expires_at = datetime.now(UTC) - timedelta(seconds=10)

    with respx.mock:
        respx.post("https://sb2login.example.com/oauth/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "new_token",
                    "refresh_token": "new_refresh",
                    "expires_in": 600,
                    "token_type": "bearer",
                },
            )
        )

        token = await auth.get_access_token()
        assert token == "new_token"
        assert auth._refresh_token == "new_refresh"


def test_invalidate_clears_tokens(auth: ServiceChannelAuth) -> None:
    """invalidate() empties the cached token data."""
    auth._access_token = "x"
    auth._refresh_token = "y"
    auth._expires_at = datetime.now(UTC)
    auth.invalidate()
    assert auth._access_token is None
    assert auth._refresh_token is None
    assert auth._expires_at is None
