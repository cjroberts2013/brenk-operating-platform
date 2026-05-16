"""Shared fixtures for integration tests.

Provides helpers for minting Supabase-shaped JWTs signed with the same
secret the backend verifies against. Lets tests run end-to-end without
spinning up a real Supabase Auth instance.
"""

from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt

from app.core.config import get_settings


def mint_jwt(
    sub: str = "00000000-0000-0000-0000-000000000001",
    email: str = "test@example.com",
    role: str = "authenticated",
    audience: str = "authenticated",
    expires_in_seconds: int = 3600,
    secret: str | None = None,
) -> str:
    """Forge a Supabase-shaped HS256 JWT. Tests use this to call protected
    endpoints without needing a real Supabase Auth round-trip.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": sub,
        "email": email,
        "role": role,
        "aud": audience,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in_seconds)).timestamp()),
    }
    return jwt.encode(
        payload,
        secret if secret is not None else settings.SUPABASE_JWT_SECRET,
        algorithm="HS256",
    )


@pytest.fixture
def valid_jwt() -> str:
    """A fresh JWT valid for 1 hour. Use in `Authorization: Bearer <token>`."""
    return mint_jwt()


@pytest.fixture
def auth_headers(valid_jwt: str) -> dict[str, str]:
    """A ready-made Authorization header dict for use as httpx default_headers."""
    return {"Authorization": f"Bearer {valid_jwt}"}
