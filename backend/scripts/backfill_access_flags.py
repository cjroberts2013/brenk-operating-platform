"""Backfill customer-unit access flags on existing work orders.

Scans every OPEN / IN PROGRESS work order's description plus its
UsersNote notes with the same detector the sync hooks use
(app/services/access_flags.py), and stamps the flag on matches. New WOs
and new notes are scanned automatically by the sync; this covers what
already existed before the feature shipped.

Idempotent: WOs that already carry a flag (active OR dismissed) are
skipped — a re-run never overwrites operator decisions.

Usage:
    python scripts/backfill_access_flags.py                     # dev, DRY RUN
    python scripts/backfill_access_flags.py --commit            # dev, write
    python scripts/backfill_access_flags.py .env.production --commit
"""

import asyncio
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

# Statuses whose WOs are still actionable — completed/canceled history
# doesn't need call-ahead flags.
_AT_RISK_STATUSES = ("OPEN", "IN PROGRESS")


def _inject_env(env_path: Path) -> None:
    """Load DATABASE_URL* from the chosen env file BEFORE app imports, so
    `--commit .env.production` actually targets prod (see the remap-script
    fix in git history for why this must precede the imports)."""
    if not env_path.exists():
        raise SystemExit(f"env file not found: {env_path}")
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key.startswith("DATABASE_URL"):
            os.environ[key] = value.strip().strip('"').strip("'")


async def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--commit"]
    commit = "--commit" in sys.argv[1:]
    env_arg = args[0] if args else ".env"
    _inject_env(BACKEND_ROOT / env_arg)

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.orm import selectinload
    from sqlalchemy.pool import NullPool

    from app.core.config import get_settings
    from app.models.work_order import WorkOrder
    from app.services.access_flags import apply_description_flag, apply_note_flag

    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL_ASYNC, poolclass=NullPool)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    mode = "COMMIT" if commit else "DRY RUN"
    print(f"\n=== Access-flag backfill ({env_arg}, {mode}) ===\n")

    flagged = 0
    async with factory() as session:
        stmt = (
            select(WorkOrder)
            .options(selectinload(WorkOrder.notes))
            .where(WorkOrder.primary_status.in_(_AT_RISK_STATUSES))
        )
        wos = (await session.execute(stmt)).scalars().all()
        print(f"scanning {len(wos)} open/in-progress work orders…\n")

        for wo in wos:
            if wo.brenk_access_flag_at is not None:
                continue  # already flagged or operator-handled; never overwrite
            hit = apply_description_flag(wo)
            if not hit:
                for note in sorted(wo.notes, key=lambda n: n.id):
                    if apply_note_flag(wo, note):
                        hit = True
                        break
            if hit:
                flagged += 1
                print(
                    f"  WO {wo.sc_number} [{wo.brenk_access_flag_source}]: "
                    f"{(wo.brenk_access_flag_snippet or '')[:110]}"
                )

        if commit:
            await session.commit()
        else:
            await session.rollback()

    await engine.dispose()
    print(f"\n{flagged} work order(s) {'flagged' if commit else 'WOULD be flagged'}.")
    if not commit:
        print("Re-run with --commit to write.")


if __name__ == "__main__":
    asyncio.run(main())
