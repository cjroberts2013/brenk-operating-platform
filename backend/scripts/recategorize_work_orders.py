"""Re-categorize existing work orders against the current job-type taxonomy.

Re-runs the Gemini categorizer so WOs filed under the old 16-type list get
re-sorted into the richer list (Windows & Glass, Appliance Repair, Parking Lot
Striping, Drywall, Locksmith, Security, …).

Only touches WOs whose category is AI-sourced or empty — `manual` and
`confirmed` categories are operator decisions and are left alone. One small
Flash-Lite call per WO; the run is bounded by the WOs that qualify.

    python scripts/recategorize_work_orders.py            # dry run (still calls
                                                          # the API to preview)
    python scripts/recategorize_work_orders.py --commit
    python scripts/recategorize_work_orders.py --commit .env.production
"""

import asyncio
import os
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))


def _inject_env(env_path: Path) -> None:
    """Load DATABASE_URL*/GEMINI_* from the chosen env file into os.environ
    BEFORE the app config is imported, so the script targets the right DB."""
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


NEW_TYPES = {
    "Windows & Glass",
    "Appliance Repair",
    "Parking Lot Striping",
    "Drywall",
    "Locksmith",
    "Security",
}


async def main() -> None:
    commit = "--commit" in sys.argv
    env_arg = next((a for a in sys.argv[1:] if not a.startswith("--")), ".env")
    _inject_env(BACKEND_ROOT / env_arg)

    # Imported AFTER env injection so the right database is used.
    from sqlalchemy import or_, select
    from sqlalchemy.orm import selectinload

    from app.core.config import get_settings
    from app.db.session import AsyncSessionLocal
    from app.models.work_order import WorkOrder
    from app.services.categorize import categorize
    from app.services.job_types import list_job_types

    if not get_settings().GEMINI_API_KEY:
        print("No GEMINI_API_KEY set — nothing to do.")
        return
    print(f"=== Re-categorize ({env_arg}) ===")

    async with AsyncSessionLocal() as session:
        defs = [(jt.name, jt.description or "") for jt in await list_job_types(session)]

        rows = (
            (
                await session.execute(
                    select(WorkOrder)
                    .options(selectinload(WorkOrder.trade))
                    .where(
                        WorkOrder.description.is_not(None),
                        or_(
                            WorkOrder.brenk_category_source == "ai",
                            WorkOrder.brenk_category.is_(None),
                        ),
                    )
                    .order_by(WorkOrder.sc_work_order_id.desc())
                )
            )
            .scalars()
            .all()
        )

        print(f"Re-categorizing {len(rows)} AI/uncategorized work orders…\n")
        changed = 0
        moved_to_new = 0
        for wo in rows:
            trade_hint = wo.trade.name if wo.trade else None
            result = await categorize(wo.description, trade_hint=trade_hint, job_type_defs=defs)
            if result is None:
                continue
            category, confidence = result
            old = wo.brenk_category
            if category != old:
                changed += 1
                if category in NEW_TYPES:
                    moved_to_new += 1
                print(f"  WO {wo.sc_number}: {old or '—'} -> {category}")
            wo.brenk_category = category
            wo.brenk_category_ai = category
            wo.brenk_category_source = "ai"
            wo.brenk_category_confidence = Decimal(str(round(confidence, 3)))
            wo.brenk_category_at = datetime.now(UTC)

        print(f"\n{len(rows)} scanned · {changed} changed · {moved_to_new} moved to a new type")
        if commit:
            await session.commit()
            print("COMMITTED.")
        else:
            await session.rollback()
            print("DRY RUN — re-run with --commit to save.")


if __name__ == "__main__":
    asyncio.run(main())
