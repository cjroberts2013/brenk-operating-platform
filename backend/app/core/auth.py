"""Supabase JWT authentication for FastAPI endpoints.

Supabase Auth issues JWTs (HS256 by default) signed with the project's
JWT secret. The frontend presents the JWT in the Authorization header;
this module validates it server-side and exposes the authenticated user
as a FastAPI dependency.

Required claims:
- `sub`: user UUID (becomes CurrentUser.id)
- `aud`: must be "authenticated" — Supabase emits this for signed-in users
- `exp`: validated by jose (raises ExpiredSignatureError if past)

Optional claims surfaced on CurrentUser when present: `email`, `role`.

Get the JWT secret from Supabase → Project Settings → API → JWT Settings.
It must be set in `SUPABASE_JWT_SECRET` for any of this to work.
"""

from typing import Annotated

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt
from pydantic import BaseModel

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

_SUPABASE_AUDIENCE = "authenticated"
_SUPABASE_ALGORITHM = "HS256"

_bearer_scheme = HTTPBearer(
    bearerFormat="JWT",
    description="Paste a Supabase access token (JWT). The frontend obtains "
    "one from Supabase Auth; for ad-hoc testing, generate one via the "
    "Supabase dashboard or scripts/mint_dev_token.py.",
)


class CurrentUser(BaseModel):
    """The authenticated subject extracted from a verified JWT."""

    id: str
    email: str | None = None
    role: str | None = None


def _credentials_exception(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
) -> CurrentUser:
    """Validate a Supabase JWT from the Authorization header.

    Returns a CurrentUser populated from the token's claims, or raises
    401 with a useful detail message on any validation failure.
    """
    settings = get_settings()
    if not settings.SUPABASE_JWT_SECRET:
        logger.error("SUPABASE_JWT_SECRET is unset; rejecting all auth attempts")
        raise _credentials_exception("auth is misconfigured on the server")

    token = credentials.credentials

    try:
        claims = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=[_SUPABASE_ALGORITHM],
            audience=_SUPABASE_AUDIENCE,
        )
    except ExpiredSignatureError as exc:
        raise _credentials_exception("token has expired") from exc
    except JWTError as exc:
        raise _credentials_exception(f"invalid token: {exc}") from exc

    sub = claims.get("sub")
    if not sub:
        raise _credentials_exception("token missing required 'sub' claim")

    return CurrentUser(
        id=sub,
        email=claims.get("email"),
        role=claims.get("role"),
    )
