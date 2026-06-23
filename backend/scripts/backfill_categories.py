"""Backfill Brenk job categories on existing work orders via Gemini.

Categorizes every WO that doesn't yet have `brenk_category`, in capped
batches, until none remain (or an overall safety cap is hit). Idempotent —
re-running only touches still-uncategorized WOs. Uses the DB + GEMINI_API_KEY
from the chosen env file.

Usage:
    python scripts/backfill_categories.py              # dev (.env)
    python scripts/backfill_categories.py .env.production   # prod

Costs: text-only Flash Lite, ~one tiny call per WO. Set GEMINI_MODEL in the
env if the default model id is wrong.
"""

import asyncio
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

# Overall safety cap across all batches (well above Brenk's ~400 WOs).
MAX_TOTAL = 2000
BATCH = 50


def _inject_env(env_path: Path) -> None:
    if not env_path.exists():
        raise SystemExit(f"env file not found: {env_path}")
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key.startswith(("DATABASE_URL", "GEMINI_")):
            os.environ[key] = value.strip().strip('"').strip("'")


async def main() -> None:
    env_arg = sys.argv[1] if len(sys.argv) > 1 else ".env"
    _inject_env(BACKEND_ROOT / env_arg)

    from app.core.config import get_settings
    from app.db.session import AsyncSessionLocal
    from app.services.categorize import categorize_uncategorized

    settings = get_settings()
    print(f"\n=== Category backfill ({env_arg}) ===")
    print(f"model: {settings.GEMINI_MODEL}")
    if not settings.GEMINI_API_KEY:
        raise SystemExit("GEMINI_API_KEY not set in this env — nothing to do.")

    total = 0
    while total < MAX_TOTAL:
        async with AsyncSessionLocal() as session:
            result = await categorize_uncategorized(session, limit=BATCH)
        print(f"  batch: {result}")
        total += result["categorized"]
        # Stop on no progress: either nothing left to scan, or the only
        # remaining uncategorized WOs are ones Gemini can't classify (no
        # usable text) — both surface as categorized == 0, which avoids an
        # infinite loop re-scanning the same unparseable rows.
        if result["categorized"] == 0:
            break

    print(f"=== done — categorized {total} work order(s) ===\n")


if __name__ == "__main__":
    asyncio.run(main())
