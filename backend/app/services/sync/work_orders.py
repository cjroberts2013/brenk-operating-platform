"""Work order sync orchestration.

Glues the ServiceChannel client to the upserter. Each WO is committed in
its own transaction so a single malformed payload doesn't poison the
batch.

There is intentionally no recency filter. SC's /v3/workorders endpoint has
no `updatedSince` parameter (confirmed via Swagger), and a client-side
filter on `UpdatedDate` would risk silently dropping long-lived in-progress
work orders whose state we still care about. Instead we paginate
everything every tick and rely on upsert idempotency — the upserter
no-ops on unchanged records and only emits status-history rows when a WO
actually moves. At Brenk's scale (~8 new WOs/day, sandbox ~327 total)
the cost of a full sweep every 5 minutes is negligible.

Notes are fetched conditionally: only when the WO's `notes_count` from the
list payload differs from what we have stored. Avoids hammering SC with
one extra request per WO per tick (~327 requests, would exceed sandbox
rate limit). New notes typically arrive on only a handful of WOs per
tick.
"""

from typing import Any

import structlog
from sqlalchemy import func, select

from app.db.session import AsyncSessionLocal
from app.models.work_order import WorkOrderNote
from app.services.servicechannel.client import ServiceChannelClient
from app.services.sync.notes import sync_notes_for_work_order
from app.services.sync.upserter import upsert_work_order

logger = structlog.get_logger(__name__)


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

    summary: dict[str, Any] = {
        "fetched": 0,
        "upserted": 0,
        "notes_synced": 0,
        "errors": [],
    }

    async for payload in client.iter_work_orders(max_pages=max_pages):
        summary["fetched"] += 1
        sc_id = payload.get("Id")
        incoming_notes_count = (
            (payload.get("Notes") or {}).get("Count", {}).get("Total", 0)
        )

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

    logger.info(
        "work order sync complete",
        fetched=summary["fetched"],
        upserted=summary["upserted"],
        notes_synced=summary["notes_synced"],
        errors=len(summary["errors"]),
    )
    return summary
