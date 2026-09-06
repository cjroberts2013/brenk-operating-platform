"""Work order sync orchestration.

Glues the ServiceChannel client to the upserter. Each WO is committed in
its own transaction so a single malformed payload doesn't poison the
batch.

Two-pass design:

1. **List sweep.** Paginate SC's /v3/workorders and upsert each. SC has no
   `updatedSince` param (confirmed via Swagger) so we take the whole feed.

2. **Reconcile dropped WOs.** SC's list feed only returns *active* work
   orders — once a WO is COMPLETED it silently drops off the list, so the
   sweep above never sees the completion and our copy stays frozen at its
   last active status (e.g. IN PROGRESS/DISPATCH CONFIRMED) forever. That
   made completed WOs linger on the dashboard as "180 days overdue"
   (found 2026-09-06 — 98 stuck WOs in prod, all actually COMPLETED in SC).
   So after the sweep, any local WO still in a non-terminal status whose
   `last_synced_at` the sweep did NOT bump (i.e. SC didn't return it) is
   re-fetched individually via GET /v3/workorders/{id} — which DOES return
   completed WOs — and upserted, catching the missed transition.

Notes are fetched conditionally: only when the WO's `notes_count` from the
list payload differs from what we have stored. Avoids hammering SC with
one extra request per WO per tick (~327 requests, would exceed sandbox
rate limit). New notes typically arrive on only a handful of WOs per
tick.
"""

from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import func, or_, select, update

from app.core.exceptions import ServiceChannelNotFoundError
from app.db.session import AsyncSessionLocal
from app.models.work_order import WorkOrder, WorkOrderNote
from app.services.servicechannel.client import ServiceChannelClient
from app.services.sync.notes import sync_notes_for_work_order
from app.services.sync.upserter import upsert_work_order

logger = structlog.get_logger(__name__)

# Non-terminal statuses — WOs here are still "in flight" for us. SC drops
# them from the list feed once they COMPLETE, so these are the ones the
# reconcile pass re-checks individually. Mirrors deadlines.is_at_risk_status.
_NON_TERMINAL_STATUSES = ("OPEN", "IN PROGRESS")

# Cap on individual re-fetches per tick — bounds the added request volume.
# Comfortably above the current backlog (~98) so it clears in one run;
# steady state is a handful.
_RECONCILE_CAP = 200


async def sync_all_work_orders(
    sc_client: ServiceChannelClient | None = None,
    max_pages: int = 200,
) -> dict[str, Any]:
    """Fetch every work order from SC and upsert each into the database.

    For each WO, if the incoming `notes_count` differs from what we have
    stored, also fetch and upsert the full notes thread for that WO.

    Args:
        sc_client: Optional injected client for testing.
        max_pages: Hard cap on pagination — passed through to the SC client.

    Returns:
        Summary: {"fetched", "upserted", "notes_synced", "errors"}.
        Errors are recorded per-WO; one failure does not abort the batch.
    """
    client = sc_client or ServiceChannelClient()

    logger.info("work order sync starting")

    # Anything the list sweep upserts gets last_synced_at = now() >= this.
    # Non-terminal WOs still below it afterward are ones SC didn't return.
    sweep_started = datetime.now(UTC)

    summary: dict[str, Any] = {
        "fetched": 0,
        "upserted": 0,
        "notes_synced": 0,
        "reconciled": 0,
        "marked_deleted": 0,
        "errors": [],
    }

    async for payload in client.iter_work_orders(max_pages=max_pages):
        summary["fetched"] += 1
        sc_id = payload.get("Id")
        incoming_notes_count = (payload.get("Notes") or {}).get("Count", {}).get("Total", 0)

        try:
            async with AsyncSessionLocal() as session:
                wo = await upsert_work_order(session, payload)
                summary["upserted"] += 1

                # Trigger notes sync when SC reports more notes than we
                # have actual wo_notes rows for. Comparing against the
                # stored row count (not the WO's denormalized
                # notes_count column) means we naturally backfill notes
                # for WOs that were synced before notes-sync existed.
                # Deletions in SC (incoming < stored) leave stale local
                # rows — see TODO in notes.py.
                if incoming_notes_count > 0:
                    stored_notes_count = (
                        await session.execute(
                            select(func.count())
                            .select_from(WorkOrderNote)
                            .where(WorkOrderNote.work_order_id == wo.id)
                        )
                    ).scalar_one()
                    if incoming_notes_count > stored_notes_count:
                        n = await sync_notes_for_work_order(session, client, wo)
                        summary["notes_synced"] += n

                await session.commit()
        except Exception as exc:
            logger.exception("work order upsert failed", sc_work_order_id=sc_id)
            summary["errors"].append({"sc_work_order_id": sc_id, "error": str(exc)})

    # Pass 2: reconcile WOs SC dropped from the list feed (see module docstring).
    summary["reconciled"] = await _reconcile_dropped_work_orders(client, sweep_started, summary)

    logger.info(
        "work order sync complete",
        fetched=summary["fetched"],
        upserted=summary["upserted"],
        notes_synced=summary["notes_synced"],
        reconciled=summary["reconciled"],
        marked_deleted=summary["marked_deleted"],
        errors=len(summary["errors"]),
    )
    return summary


async def _reconcile_dropped_work_orders(
    client: ServiceChannelClient,
    sweep_started: datetime,
    summary: dict[str, Any],
) -> int:
    """Re-fetch non-terminal WOs the list sweep didn't return, to catch a
    completion SC dropped from the feed. Returns the count updated.

    A WO is a candidate when its status is still non-terminal locally AND
    its `last_synced_at` predates this sync (so the list sweep didn't touch
    it → SC no longer lists it). Each is fetched individually and upserted;
    a 404 (WO purged from SC) is skipped, not fatal.
    """
    async with AsyncSessionLocal() as session:
        stmt = (
            select(WorkOrder.sc_work_order_id)
            .where(WorkOrder.primary_status.in_(_NON_TERMINAL_STATUSES))
            # Skip WOs already known-deleted, so a purged WO isn't re-404'd
            # every tick forever.
            .where(WorkOrder.brenk_sc_deleted_at.is_(None))
            .where(
                or_(
                    WorkOrder.last_synced_at < sweep_started,
                    WorkOrder.last_synced_at.is_(None),
                )
            )
            .order_by(WorkOrder.last_synced_at.asc().nullsfirst())
            .limit(_RECONCILE_CAP)
        )
        candidate_ids = list((await session.execute(stmt)).scalars().all())

    if not candidate_ids:
        return 0

    logger.info("reconcile: re-fetching WOs SC dropped from the feed", count=len(candidate_ids))
    reconciled = 0
    for sc_id in candidate_ids:
        try:
            payload = await client.get_work_order(sc_id)
            async with AsyncSessionLocal() as session:
                await upsert_work_order(session, payload)
                await session.commit()
            reconciled += 1
        except ServiceChannelNotFoundError:
            # WO deleted/voided in SC (404). Keep the row for history but
            # mark it so deadline/at-risk tracking drops it — it was showing
            # as a phantom "overdue" with a frozen status. Cleared
            # automatically if the WO ever reappears (see upsert_work_order).
            async with AsyncSessionLocal() as session:
                await session.execute(
                    update(WorkOrder)
                    .where(WorkOrder.sc_work_order_id == sc_id)
                    .values(brenk_sc_deleted_at=datetime.now(UTC))
                )
                await session.commit()
            summary["marked_deleted"] = summary.get("marked_deleted", 0) + 1
            logger.info("reconcile: WO deleted in SC — marked", sc_work_order_id=sc_id)
        except Exception as exc:
            logger.exception("reconcile fetch failed", sc_work_order_id=sc_id)
            summary["errors"].append({"sc_work_order_id": sc_id, "error": str(exc)})
    return reconciled
