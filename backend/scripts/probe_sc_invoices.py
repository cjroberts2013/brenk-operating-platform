"""Probe ServiceChannel's invoice endpoints for the Phase 1.5 spike.

Re-tests the invoice API surface documented in
docs/architecture/servicechannel-api.md -> "Invoice endpoints —
Phase 1.5 anchor". Read endpoints run by default and are 100% safe.

The write-scope check (POST /v3/invoices) is OPT-IN via the `post`
arg. It sends a deliberately INVALID body (a nonexistent WoIdentifier)
so SC cannot attach it to a real work order, i.e. it can't create a
real invoice in CubeSmart's data. Its only purpose is to read the
error CLASS back: a 401/"security permissions"/504 means we lack write
scope (Phase 1.5 blocked); a 400/404/422 content error means we DO
have write scope and just sent a bad payload.

Usage:
    python scripts/probe_sc_invoices.py                      # reads, sandbox (.env)
    python scripts/probe_sc_invoices.py .env.production      # reads, prod SC
    python scripts/probe_sc_invoices.py .env 2014917186      # override subscriber id
    python scripts/probe_sc_invoices.py .env 2014917186 post # also run write-scope check

Prints findings to the console only. Does NOT write sample files —
prod payloads contain real client/location names (confidential).
"""

import asyncio
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

# CubeSmart's SC subscriber id in Sandbox2 (per the 2026-05-25 spike).
# Production uses a different id — pass it as the 2nd CLI arg.
DEFAULT_SUBSCRIBER_ID = "2014917186"


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


async def _probe(client, label, method, path, params=None, json=None):
    """Run one request, print a compact result line, return the payload."""
    from app.core.exceptions import (
        ServiceChannelError,
        ServiceChannelNotFoundError,
    )

    try:
        payload = await client._request(method, path, params=params, json=json)
    except ServiceChannelNotFoundError:
        print(f"  [404] {label}: {method} {path}")
        return {"__error__": 404}
    except ServiceChannelError as exc:
        # Message is "SC API error: <status> <body>" — surface it whole so
        # we can see permission (401/504) vs validation (400/422) classes.
        print(f"  [err] {label}: {exc}")
        return {"__error__": str(exc)}
    except Exception as exc:
        print(f"  [err] {label}: {type(exc).__name__}: {exc}")
        return {"__error__": repr(exc)}

    if isinstance(payload, dict) and "value" in payload:
        print(f"  [ok]  {label}: OData collection, {len(payload['value'])} item(s)")
    elif isinstance(payload, list):
        print(f"  [ok]  {label}: list, {len(payload)} item(s)")
    else:
        print(f"  [ok]  {label}: {type(payload).__name__}")
    return payload


async def main() -> None:
    args = sys.argv[1:]
    env_arg = args[0] if len(args) > 0 else ".env"
    subscriber_id = args[1] if len(args) > 1 else DEFAULT_SUBSCRIBER_ID
    do_post = len(args) > 2 and args[2].lower() == "post"

    _inject_env(BACKEND_ROOT / env_arg)

    from app.core.config import get_settings
    from app.services.servicechannel import ServiceChannelAuth, ServiceChannelClient

    settings = get_settings()
    print("\n=== SC Invoice Endpoint Probe (Phase 1.5) ===")
    print(f"env file:      {env_arg}")
    print(f"environment:   {settings.SC_ENVIRONMENT}")
    print(f"api url:       {settings.SC_API_URL}")
    print(f"subscriber id: {subscriber_id}")
    print(f"write check:   {'YES (POST with bogus WO)' if do_post else 'no (reads only)'}\n")

    client = ServiceChannelClient(auth=ServiceChannelAuth())

    # --- Read path (safe) ----------------------------------------------------
    print("[1] GET /v3/invoices/{sub}/InvoiceRequirements  (config for submit payload)")
    reqs = await _probe(
        client,
        "InvoiceRequirements",
        "GET",
        f"/v3/invoices/{subscriber_id}/InvoiceRequirements",
    )
    if isinstance(reqs, dict) and "__error__" not in reqs:
        for k in (
            "RequireResolutionText",
            "RequireApprovalText",
            "DaysBeforePostingDate",
            "MaxDaysAfterPostingDate",
            "IsInvoiceNumberValidationFeatureEnabled",
            "IsInvoiceNegativeFeatureEnabled",
        ):
            if k in reqs:
                print(f"        {k} = {reqs[k]}")

    print("\n[2] GET /v3/invoices/{sub}/InvoiceRejectionReasons")
    await _probe(
        client,
        "InvoiceRejectionReasons",
        "GET",
        f"/v3/invoices/{subscriber_id}/InvoiceRejectionReasons",
    )

    print("\n[3] GET /v3/invoices/statistics")
    stats = await _probe(client, "statistics", "GET", "/v3/invoices/statistics")
    if isinstance(stats, dict) and "__error__" not in stats:
        print(f"        {stats}")

    print("\n[4] GET /v3/odata/invoices  (the auto-derive-paid blocker — recheck scope)")
    await _probe(
        client,
        "odata/invoices",
        "GET",
        "/v3/odata/invoices",
        params={"$top": 1},
    )

    # --- Write-scope check (opt-in, safe by construction) --------------------
    if do_post:
        print("\n[5] POST /v3/invoices  (write-scope check — BOGUS WoIdentifier, creates nothing)")
        body = {
            # Alphanumeric only to satisfy CubeSmart's ^\w*$ number rule, so
            # the ONLY rejection reason is the bogus WO (not the number format).
            "InvoiceNumber": "BRENKSCOPEPROBE",
            "WoIdentifier": "000000000",  # nonexistent WO: cannot attach
            "InvoiceDate": "2026-01-01T00:00:00Z",
            "InvoiceDateDTO": "2026-01-01T00:00:00Z",
        }
        result = await _probe(client, "POST /invoices", "POST", "/v3/invoices", json=body)
        err = result.get("__error__") if isinstance(result, dict) else None
        print("\n        Interpretation:")
        if err is None:
            print("        - Got a 2xx. We HAVE write scope (and SC accepted a bogus WO?!).")
        elif isinstance(err, str) and ("401" in err or "security permission" in err.lower() or "504" in err):
            print("        - Permission/scope error => NO write scope. Phase 1.5 push still BLOCKED.")
        elif isinstance(err, str) and any(c in err for c in ("400", "404", "422")):
            print("        - Content/validation error => we DO have write scope; only the payload was bad.")
            print("          Phase 1.5 invoice push is UNBLOCKED on the auth side.")
        else:
            print(f"        - Inconclusive: {err}")
    else:
        print("\n[5] POST /v3/invoices write-scope check skipped.")
        print("    Re-run with the `post` arg to test write scope (uses a bogus WO, creates nothing):")
        print(f"      python scripts/probe_sc_invoices.py {env_arg} {subscriber_id} post")

    print("\n=== done ===\n")


if __name__ == "__main__":
    asyncio.run(main())
