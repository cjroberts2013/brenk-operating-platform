"""Probe ServiceChannel for the employee -> assigned-WO mapping.

Read-only. Retries the May 19 probe against LIVE PRODUCTION data.

RESULT (2026-05-30): NOT FOUND. `Assignee` is empty across the entire
prod WO set, `/v3/odata/employees` 404s, and the WO `Provider` relation
is Brenk-the-account, not a named tech. Kept as a re-runnable artifact
in case SC's behavior or our API scope changes. Full write-up in
docs/architecture/servicechannel-api.md -> "Production probe results
(2026-05-30)".

Usage:
    python scripts/probe_sc_assignee.py                 # uses .env (sandbox)
    python scripts/probe_sc_assignee.py .env.production  # probe prod SC

Prints findings to the console only. Does NOT write sample files —
prod payloads contain real client/location/employee names (treat as
confidential, never commit).
"""

import asyncio
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))


def _inject_env(env_path: Path) -> None:
    """Load SC_* keys from an env file into os.environ before settings load.

    pydantic-settings gives real environment variables precedence over the
    baked-in env_file=".env", so this lets us point the probe at prod
    without touching config.
    """
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


async def _probe(client, label, method, path, params=None):
    """Run one probe request, print a compact result line, return payload."""
    from app.core.exceptions import (
        ServiceChannelError,
        ServiceChannelNotFoundError,
    )

    try:
        payload = await client._request(method, path, params=params)
    except ServiceChannelNotFoundError:
        print(f"  [404] {label}: {method} {path}")
        return None
    except ServiceChannelError as exc:
        print(f"  [err] {label}: {exc}")
        return None
    except Exception as exc:
        print(f"  [err] {label}: {type(exc).__name__}: {exc}")
        return None

    if isinstance(payload, dict) and "value" in payload:
        n = len(payload["value"])
        print(f"  [ok]  {label}: OData collection, {n} item(s)")
    elif isinstance(payload, list):
        print(f"  [ok]  {label}: list, {len(payload)} item(s)")
    else:
        print(f"  [ok]  {label}: {type(payload).__name__}")
    return payload


def _assignee_summary(wo: dict) -> str:
    """Describe the Assignee field on a WO dict without leaking the name."""
    if "Assignee" not in wo:
        return "no 'Assignee' key present"
    a = wo["Assignee"]
    if a in (None, "", {}, []):
        return "Assignee present but EMPTY"
    if isinstance(a, dict):
        keys = sorted(a.keys())
        has_id = bool(a.get("Id"))
        return f"Assignee dict, keys={keys}, Id populated={has_id}"
    return f"Assignee {type(a).__name__} = {a!r}"


async def main() -> None:
    env_arg = sys.argv[1] if len(sys.argv) > 1 else ".env"
    _inject_env(BACKEND_ROOT / env_arg)

    from app.core.config import get_settings
    from app.services.servicechannel import ServiceChannelAuth, ServiceChannelClient

    settings = get_settings()
    print("\n=== SC Assignee Probe ===")
    print(f"env file:    {env_arg}")
    print(f"environment: {settings.SC_ENVIRONMENT}")
    print(f"api url:     {settings.SC_API_URL}\n")

    client = ServiceChannelClient(auth=ServiceChannelAuth())

    # 1. List a small batch and inspect the Assignee field on the list shape.
    print("[1] /v3/workorders (list shape) — does Assignee come back inline?")
    page = await client.list_work_orders_page(page=1, page_size=10)
    print(f"      fetched {len(page)} WOs")
    populated_ids = []
    for wo in page:
        summary = _assignee_summary(wo)
        if "EMPTY" not in summary and "no 'Assignee'" not in summary:
            populated_ids.append(wo.get("Id") or wo.get("Number"))
    if page:
        print(f"      sample[0]: {_assignee_summary(page[0])}")
    print(f"      WOs in this page with a populated Assignee: {len(populated_ids)}/{len(page)}")

    # 2. Per-WO detail — the field may only hydrate on the single-WO endpoint.
    print("\n[2] /v3/workorders/{id} (detail shape) — first 5 from the page")
    detail_hits = 0
    for wo in page[:5]:
        wo_id = wo.get("Id")
        if wo_id is None:
            continue
        detail = await client.get_work_order(wo_id)
        summary = _assignee_summary(detail) if isinstance(detail, dict) else "non-dict"
        if isinstance(detail, dict) and "EMPTY" not in summary and "no 'Assignee'" not in summary:
            detail_hits += 1
        print(f"      WO {wo_id}: {summary}")
    print(f"      detail endpoint Assignee hits: {detail_hits}/{min(5, len(page))}")

    # 3. OData employees collection — does it even exist in prod?
    print("\n[3] /v3/odata/employees — sibling collection probe")
    await _probe(client, "employees", "GET", "/v3/odata/employees", params={"$top": 5})

    # 4. employees $expand=WorkOrders — nav property for assignments?
    print("\n[4] /v3/odata/employees?$expand=WorkOrders")
    emp_expand = await _probe(
        client,
        "employees+WorkOrders",
        "GET",
        "/v3/odata/employees",
        params={"$top": 5, "$expand": "WorkOrders"},
    )
    if isinstance(emp_expand, dict) and emp_expand.get("value"):
        sample = emp_expand["value"][0]
        print(f"      employee[0] keys: {sorted(sample.keys())}")

    # 5. OData workorders — the live lead. The OData collection schema
    #    DOES carry an `Assignee` field (the REST endpoint does not). Pull a
    #    batch and measure how many carry a populated Assignee.
    print("\n[5] /v3/odata/workorders?$select=Id,Number,Assignee — population rate")
    od_wo = await _probe(
        client,
        "odata workorders",
        "GET",
        "/v3/odata/workorders",
        params={"$top": 50, "$select": "Id,Number,Assignee", "$orderby": "Id desc"},
    )
    if isinstance(od_wo, dict) and od_wo.get("value"):
        rows = od_wo["value"]
        populated = [r for r in rows if r.get("Assignee") not in (None, "", {}, [])]
        print(f"      odata WO[0] Assignee: {_assignee_summary(rows[0])}")
        print(f"      populated Assignee: {len(populated)}/{len(rows)}")
        if populated:
            ex = populated[0]["Assignee"]
            shape = sorted(ex.keys()) if isinstance(ex, dict) else type(ex).__name__
            print(f"      populated Assignee shape: {shape}")

    # 6. OData workorders with $expand=Assignee — hydrate the complex type
    print("\n[6] /v3/odata/workorders?$expand=Assignee — does the nav hydrate?")
    od_exp = await _probe(
        client,
        "odata WO+Assignee",
        "GET",
        "/v3/odata/workorders",
        params={"$top": 5, "$expand": "Assignee", "$orderby": "Id desc"},
    )
    if isinstance(od_exp, dict) and od_exp.get("value"):
        for r in od_exp["value"][:5]:
            print(f"      WO {r.get('Number') or r.get('Id')}: {_assignee_summary(r)}")

    print("\n=== done ===\n")


if __name__ == "__main__":
    asyncio.run(main())
