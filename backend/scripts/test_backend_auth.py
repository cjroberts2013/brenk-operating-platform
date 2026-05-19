"""End-to-end check that the backend accepts Supabase-issued ES256 tokens.

Flow:
  1. POST to Supabase Auth's /token endpoint with the test user's
     email + password. Returns an access_token (signed with ES256 by
     the project's current JWT key).
  2. GET /api/v1/work-orders/?page_size=1 against our backend with
     that token in the Authorization header.
  3. Assert 200 + a sensible-looking response body.

Usage:
  python scripts/test_backend_auth.py user@example.com mypassword

The backend (uvicorn on :8000) must be running. Credentials never
leave the process — they go straight to Supabase Auth and the token
straight to localhost.
"""

import asyncio
import os
import sys
from pathlib import Path

import httpx

# Load .env so we get SUPABASE_URL and SUPABASE_ANON_KEY without
# needing the user to export them.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.core.config import get_settings  # noqa: E402


async def main(email: str, password: str) -> int:
    settings = get_settings()
    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        print(
            "ERROR: SUPABASE_URL and SUPABASE_ANON_KEY must be set in "
            "backend/.env for this script."
        )
        return 2

    backend_url = os.environ.get("BACKEND_URL", "http://localhost:8000")

    print(f"Signing in as {email} via Supabase Auth…")
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/token",
            params={"grant_type": "password"},
            json={"email": email, "password": password},
            headers={"apikey": settings.SUPABASE_ANON_KEY},
        )
        if resp.status_code != 200:
            print(f"  sign-in failed: {resp.status_code} {resp.text}")
            return 1
        token_payload = resp.json()
        access_token = token_payload["access_token"]

    # Decode the header (no verification) to confirm the signing algo —
    # mostly for diagnostic interest.
    import base64
    import json

    header_b64 = access_token.split(".", 1)[0]
    header_b64 += "=" * ((4 - len(header_b64) % 4) % 4)
    header = json.loads(base64.urlsafe_b64decode(header_b64).decode())
    print(f"  got access_token; alg={header.get('alg')} kid={header.get('kid')}")

    print(f"\nCalling backend {backend_url}/api/v1/work-orders/?page_size=1 …")
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{backend_url}/api/v1/work-orders/",
            params={"page_size": 1},
            headers={"Authorization": f"Bearer {access_token}"},
        )

    print(f"  status: {resp.status_code}")
    if resp.status_code == 200:
        body = resp.json()
        print(
            f"  total work orders accessible: {body.get('total')}; "
            f"sample item id: {body['items'][0]['id'] if body['items'] else 'none'}"
        )
        print("\n✓ backend accepts the ES256 token; JWKS verification works.")
        return 0
    else:
        print(f"  body: {resp.text[:400]}")
        print("\n✗ backend rejected the token. See above for the 401 detail.")
        return 1


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python scripts/test_backend_auth.py EMAIL PASSWORD")
        sys.exit(2)
    sys.exit(asyncio.run(main(sys.argv[1], sys.argv[2])))
