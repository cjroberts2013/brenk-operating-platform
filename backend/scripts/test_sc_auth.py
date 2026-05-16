"""Verify ServiceChannel authentication end-to-end.

Run after filling in credentials in .env:
    python scripts/test_sc_auth.py

Should print a token and fetch a small sample of work orders. This proves
the auth flow works before we wire it into the sync worker.
"""

import asyncio
import json
import sys
from pathlib import Path

# Make `app` importable when running this script directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings  # noqa: E402
from app.services.servicechannel import ServiceChannelAuth, ServiceChannelClient  # noqa: E402


async def main() -> None:
    settings = get_settings()
    print(f"\n=== ServiceChannel Auth Test ===")
    print(f"Environment: {settings.SC_ENVIRONMENT}")
    print(f"Login URL:   {settings.SC_LOGIN_URL}")
    print(f"API URL:     {settings.SC_API_URL}")
    print(f"Client ID:   {settings.SC_CLIENT_ID[:8]}...")
    print(f"Username:    {settings.SC_USERNAME}\n")

    auth = ServiceChannelAuth()
    token = await auth.get_access_token()
    print(f"[ok] Obtained access token: {token[:40]}...")
    print(f"     Expires at: {auth._expires_at}\n")

    client = ServiceChannelClient(auth=auth)
    print("Fetching a small batch of work orders...")
    work_orders = await client.list_work_orders(limit=5)

    print(f"[ok] Fetched {len(work_orders)} work orders\n")
    if work_orders:
        first = work_orders[0]
        print("First work order summary:")
        print(f"  Number:      {first.get('Number')}")
        print(f"  Status:      {first.get('Status', {}).get('Primary')}")
        print(f"  Trade:       {first.get('Trade')}")
        print(f"  Description: {(first.get('Description') or '')[:80]}...")

        sample_path = (
            Path(__file__).resolve().parent.parent.parent
            / "docs"
            / "api-samples"
            / "workorder-list-sample.json"
        )
        sample_path.parent.mkdir(parents=True, exist_ok=True)
        sample_path.write_text(json.dumps(work_orders, indent=2))
        print(f"\nSaved sample to: {sample_path}")


if __name__ == "__main__":
    asyncio.run(main())
