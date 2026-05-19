"""Supabase JWT authentication for FastAPI endpoints.

Supports two verification paths, chosen by the token's `alg` header:

1. **HS256** — verified against the shared secret in `SUPABASE_JWT_SECRET`.
   Used by the test suite (which mints its own HS256 tokens) and by any
   tokens still in circulation that were signed with Supabase's legacy
   HS256 secret before a project's JWT-signing-key rotation.

2. **ES256 / RS256** — verified against the project's JWKS public key,
   discovered via `${SUPABASE_URL}/auth/v1/.well-known/jwks.json` and
   selected by the token's `kid` header. This is the modern Supabase
   pattern after the migration to asymmetric signing keys.

The JWKS document is cached at module level for an hour. On a `kid`
miss (e.g., during a rotation) the cache is invalidated and refetched
once before giving up — handles seamless key rollover without a
backend restart.

Required claims:
- `sub`: user UUID (becomes CurrentUser.id)
- `aud`: must be "authenticated"
- `exp`: validated by jose
"""

import time
from typing import Annotated, Any

import httpx
import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt
from pydantic import BaseModel

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

_SUPABASE_AUDIENCE = "authenticated"
_SYMMETRIC_ALGORITHMS = {"HS256"}
_ASYMMETRIC_ALGORITHMS = {"ES256", "RS256"}
_JWKS_CACHE_TTL_SECONDS = 3600

_bearer_scheme = HTTPBearer(
    bearerFormat="JWT",
    description=(
        "Paste a Supabase access token (JWT). The frontend obtains one "
        "from Supabase Auth automatically; for ad-hoc API testing, get "
        "one by signing in via the dashboard and copying the cookie."
    ),
)


# -----------------------------------------------------------------------------
# JWKS cache
# -----------------------------------------------------------------------------

_jwks_cache: dict[str, Any] | None = None
_jwks_cache_at: float = 0.0


async def _fetch_jwks(*, force: bool = False) -> dict[str, Any]:
    """Return Supabase's JWKS document, refreshing the cache if stale.

    `force=True` bypasses the cache — used as a one-shot retry when a
    `kid` lookup fails, in case the project rotated keys recently.
    """
    global _jwks_cache, _jwks_cache_at
    now = time.time()
    if (
        not force
        and _jwks_cache is not None
        and (now - _jwks_cache_at) < _JWKS_CACHE_TTL_SECONDS
    ):
        return _jwks_cache

    settings = get_settings()
    if not settings.SUPABASE_URL:
        raise _credentials_exception("server misconfigured (SUPABASE_URL unset)")

    url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        _jwks_cache = response.json()
        _jwks_cache_at = now
        return _jwks_cache


async def _find_signing_key(kid: str) -> dict[str, Any]:
    """Return the JWK matching `kid`, with one cache-bust retry on miss."""
    jwks = await _fetch_jwks()
    for jwk in jwks.get("keys", []):
        if jwk.get("kid") == kid:
            return jwk

    # Maybe the cache is stale (project just rotated). Try once more.
    jwks = await _fetch_jwks(force=True)
    for jwk in jwks.get("keys", []):
        if jwk.get("kid") == kid:
            return jwk

    raise _credentials_exception(f"no signing key with kid={kid}")


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------


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


async def _verify_token(token: str) -> dict[str, Any]:
    """Verify the token by its declared algorithm and return its claims.

    Raises an HTTPException(401) on any failure. The caller need not
    re-wrap.
    """
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise _credentials_exception(f"malformed token: {exc}") from exc

    alg = header.get("alg")
    if not alg:
        raise _credentials_exception("token missing 'alg' header")

    if alg in _SYMMETRIC_ALGORITHMS:
        settings = get_settings()
        if not settings.SUPABASE_JWT_SECRET:
            logger.error("SUPABASE_JWT_SECRET unset; rejecting HS256 token")
            raise _credentials_exception("server misconfigured (no JWT secret)")
        key: Any = settings.SUPABASE_JWT_SECRET

    elif alg in _ASYMMETRIC_ALGORITHMS:
        kid = header.get("kid")
        if not kid:
            raise _credentials_exception("token missing 'kid' header")
        key = await _find_signing_key(kid)

    else:
        raise _credentials_exception(f"unsupported signing algorithm: {alg}")

    try:
        return jwt.decode(
            token,
            key,
            algorithms=[alg],
            audience=_SUPABASE_AUDIENCE,
        )
    except ExpiredSignatureError as exc:
        raise _credentials_exception("token has expired") from exc
    except JWTError as exc:
        raise _credentials_exception(f"invalid token: {exc}") from exc


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
) -> CurrentUser:
    """Validate a Supabase JWT from the Authorization header.

    Returns a CurrentUser populated from the token's claims, or raises
    401 with a useful detail message on any validation failure.
    """
    claims = await _verify_token(credentials.credentials)

    sub = claims.get("sub")
    if not sub:
        raise _credentials_exception("token missing required 'sub' claim")

    return CurrentUser(
        id=sub,
        email=claims.get("email"),
        role=claims.get("role"),
    )
