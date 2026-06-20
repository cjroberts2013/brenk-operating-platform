"""Probe ServiceChannel's work-order attachment endpoints (read-only).

Phase 0 go/no-go for the attachments feature (see
docs/architecture/servicechannel-api.md). All requests are GETs — safe.

What it resolves:
  1. Authorization: does our Provider OAuth token get 200 on
     GET /v3/odata/workorders({id})/attachments, or NotAllowed/504?
  2. Uri shape: is the returned `Uri` fetchable directly, or does it
     need our Bearer / a different host? Picks the download mechanism.

Usage:
    python scripts/probe_sc_attachments.py                 # sandbox (.env), WO 343852740
    python scripts/probe_sc_attachments.py .env 343852740  # explicit WO
    python scripts/probe_sc_attachments.py .env.production 343852740  # prod SC

Prints findings to the console only. Does NOT write sample files — prod
payloads carry real client/location names (confidential).
"""

import asyncio
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

DEFAULT_WORK_ORDER_ID = "343852740"


def _inject_env(env_path: Path) -> None:
    """Load SC_* keys from an env file into os.environ before settings load."""
    if not env_path.exists():
        raise SystemExit(f"env file not found: {env_path}")
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key.startswith("SC_"):
            os.environ[key] = value.strip().strip('"').strip("'")


async def main() -> None:
    args = sys.argv[1:]
    env_arg = args[0] if len(args) > 0 else ".env"
    work_order_id = args[1] if len(args) > 1 else DEFAULT_WORK_ORDER_ID

    _inject_env(BACKEND_ROOT / env_arg)

    import httpx

    from app.core.config import get_settings
    from app.core.exceptions import ServiceChannelError, ServiceChannelNotFoundError
    from app.services.servicechannel import ServiceChannelAuth, ServiceChannelClient

    settings = get_settings()
    print("\n=== SC Work-Order Attachments Probe (Phase 0) ===")
    print(f"env file:     {env_arg}")
    print(f"environment:  {settings.SC_ENVIRONMENT}")
    print(f"api url:      {settings.SC_API_URL}")
    print(f"work order:   {work_order_id}\n")

    client = ServiceChannelClient(auth=ServiceChannelAuth())

    # --- [1] List attachments (OData) ---------------------------------------
    path = f"/v3/odata/workorders({work_order_id})/attachments"
    print(f"[1] GET {path}")
    attachments: list | None = None
    try:
        payload = await client._request("GET", path)
    except ServiceChannelNotFoundError:
        print("  [404] not found")
        payload = None
    except ServiceChannelError as exc:
        print(f"  [err] {exc}")
        msg = str(exc).lower()
        if "notallowed" in msg or "security permission" in msg or "504" in msg or "401" in msg:
            print("  => NOT AUTHORIZED for our token. Feature blocked on SC scope.")
        payload = None
    except Exception as exc:
        print(f"  [err] {type(exc).__name__}: {exc}")
        payload = None

    if payload is not None:
        # OData may wrap in {"value": [...]} or return a bare list.
        if isinstance(payload, dict) and "value" in payload:
            attachments = payload["value"]
        elif isinstance(payload, list):
            attachments = payload
        else:
            attachments = []
        print(f"  [ok] authorized — {len(attachments)} attachment(s)")
        for i, att in enumerate(attachments):
            keys = sorted(att.keys()) if isinstance(att, dict) else "?"
            print(f"    [{i}] keys={keys}")
            if isinstance(att, dict):
                print(
                    f"        Id={att.get('Id')} Name={att.get('Name')!r} NoteId={att.get('NoteId')}"
                )
                print(f"        Uri={att.get('Uri')!r}")

    # --- [2] Try to fetch the first attachment's Uri ------------------------
    if attachments:
        uri = attachments[0].get("Uri") if isinstance(attachments[0], dict) else None
        if not uri:
            print("\n[2] first attachment has no Uri — cannot test download.")
        else:
            print(f"\n[2] Fetch the Uri to learn how downloads work:\n    {uri}")
            token = await client.auth.get_access_token()
            is_absolute = uri.startswith("http://") or uri.startswith("https://")
            full = uri if is_absolute else f"{settings.SC_API_URL}{uri}"
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as hc:
                # a) no auth
                try:
                    r = await hc.get(full)
                    print(
                        f"    no-auth   → {r.status_code} "
                        f"type={r.headers.get('content-type')} bytes={len(r.content)}"
                    )
                except Exception as exc:
                    print(f"    no-auth   → error: {type(exc).__name__}: {exc}")
                # b) with our SC bearer
                try:
                    r = await hc.get(full, headers={"Authorization": f"Bearer {token}"})
                    print(
                        f"    w/ bearer → {r.status_code} "
                        f"type={r.headers.get('content-type')} bytes={len(r.content)}"
                    )
                except Exception as exc:
                    print(f"    w/ bearer → error: {type(exc).__name__}: {exc}")
            print(
                "\n    Interpretation: a 200 with image/* or application/* bytes means the\n"
                "    Uri is directly fetchable (use that mechanism). 401/403 on both means\n"
                "    the Uri needs SC portal session auth — fall back to thumbnail/deep-link."
            )

    print("\n=== done ===\n")


if __name__ == "__main__":
    asyncio.run(main())
