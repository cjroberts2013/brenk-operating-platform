"""ServiceChannel OAuth 2.0 authentication using the Resource Owner Password Credentials grant.

Tokens are cached in-memory and refreshed automatically before expiration. The 5-second
cooldown on the /oauth/token endpoint is respected by reusing tokens until expiry.
"""

import base64
from datetime import UTC, datetime, timedelta

import httpx
import structlog

from app.core.config import get_settings
from app.core.exceptions import ServiceChannelAuthError

logger = structlog.get_logger(__name__)

# Refresh the token this many seconds before it actually expires, to avoid
# making requests with a token that expires mid-flight.
TOKEN_REFRESH_MARGIN_SECONDS = 30


class ServiceChannelAuth:
    """Manages OAuth tokens for the ServiceChannel API."""

    def __init__(
        self,
        login_url: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        settings = get_settings()
        self.login_url = login_url or settings.SC_LOGIN_URL
        self.client_id = client_id or settings.SC_CLIENT_ID
        self.client_secret = client_secret or settings.SC_CLIENT_SECRET
        self.username = username or settings.SC_USERNAME
        self.password = password or settings.SC_PASSWORD
        self.timeout_seconds = timeout_seconds or settings.SC_REQUEST_TIMEOUT_SECONDS

        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._expires_at: datetime | None = None

    @property
    def _basic_auth_header(self) -> str:
        """Base64-encoded `client_id:client_secret` for the Basic auth header."""
        raw = f"{self.client_id}:{self.client_secret}".encode()
        return base64.b64encode(raw).decode()

    def _is_token_valid(self) -> bool:
        """Whether we have a non-expired access token."""
        if not self._access_token or not self._expires_at:
            return False
        margin = timedelta(seconds=TOKEN_REFRESH_MARGIN_SECONDS)
        return datetime.now(UTC) + margin < self._expires_at

    async def get_access_token(self) -> str:
        """Return a valid access token, fetching or refreshing if needed."""
        if self._is_token_valid():
            assert self._access_token is not None
            return self._access_token

        if self._refresh_token:
            try:
                await self._refresh_access_token()
                assert self._access_token is not None
                return self._access_token
            except ServiceChannelAuthError:
                logger.warning("Refresh token failed, falling back to password grant")

        await self._request_new_token()
        assert self._access_token is not None
        return self._access_token

    async def _request_new_token(self) -> None:
        """Request a new access token via the password grant."""
        logger.info("Requesting new ServiceChannel access token (password grant)")
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.login_url}/oauth/token",
                headers={
                    "Authorization": f"Basic {self._basic_auth_header}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "username": self.username,
                    "password": self.password,
                    "grant_type": "password",
                },
            )

        if response.status_code != 200:
            raise ServiceChannelAuthError(
                f"Failed to obtain access token: {response.status_code} {response.text}"
            )

        self._store_token_response(response.json())

    async def _refresh_access_token(self) -> None:
        """Refresh the access token using the refresh token."""
        if not self._refresh_token:
            raise ServiceChannelAuthError("No refresh token available")

        logger.info("Refreshing ServiceChannel access token")
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.login_url}/oauth/token",
                headers={
                    "Authorization": f"Basic {self._basic_auth_header}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "refresh_token": self._refresh_token,
                    "grant_type": "refresh_token",
                },
            )

        if response.status_code != 200:
            raise ServiceChannelAuthError(
                f"Failed to refresh access token: {response.status_code} {response.text}"
            )

        self._store_token_response(response.json())

    def _store_token_response(self, data: dict) -> None:
        """Persist the token data from a successful auth response."""
        self._access_token = data["access_token"]
        self._refresh_token = data.get("refresh_token")
        expires_in = int(data.get("expires_in", 600))
        self._expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
        logger.info(
            "Stored ServiceChannel access token",
            expires_in_seconds=expires_in,
        )

    def invalidate(self) -> None:
        """Clear cached tokens — next call will re-authenticate."""
        self._access_token = None
        self._refresh_token = None
        self._expires_at = None
