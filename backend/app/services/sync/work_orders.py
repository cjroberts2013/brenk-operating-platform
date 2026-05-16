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
"""

from typing import Any

import structlog

from app.db.session import AsyncSessionLocal
from app.services.servicechannel.client import ServiceChannelClient
from app.services.sync.upserter import upsert_work_order

logger = structlog.get_logger(__name__)


async def sync_all_work_orders(
    sc_client: ServiceChannelClient | None = None,
    max_pages: int = 200,
) -> dict[str, Any]:
    """Fetch every work order from SC and upsert each into the database.

    Args:
        sc_client: Optional injected client for testing.
        max_pages: Hard cap on pagination — passed through to the SC client.

    Returns:
        Summary: {"fetched", "upserted", "errors"}. Errors are recorded
        per-WO; one failure does not abort the batch.
    """
    client = sc_client or ServiceChannelClient()

    logger.info("work order sync starting")

    summary: dict[str, Any] = {
        "fetched": 0,
        "upserted": 0,
        "errors": [],
    }

    async for payload in client.iter_work_orders(max_pages=max_pages):
        summary["fetched"] += 1
        sc_id = payload.get("Id")
        try:
            async with AsyncSessionLocal() as session:
                await upsert_work_order(session, payload)
                await session.commit()
            summary["upserted"] += 1
        except Exception as exc:
            logger.exception("work order upsert failed", sc_work_order_id=sc_id)
            summary["errors"].append({"sc_work_order_id": sc_id, "error": str(exc)})

    logger.info(
        "work order sync complete",
        fetched=summary["fetched"],
        upserted=summary["upserted"],
        errors=len(summary["errors"]),
    )
    return summary
