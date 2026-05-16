"""Work order sync orchestration.

Glues the ServiceChannel client to the upserter. Each WO is committed in its
own transaction so a single malformed payload doesn't poison the batch.

Recency filtering happens client-side: SC's /v3/workorders endpoint has no
"updated since" filter (confirmed via Swagger), so we paginate everything
and skip records older than the cutoff before upserting.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from app.db.session import AsyncSessionLocal
from app.services.servicechannel.client import ServiceChannelClient
from app.services.sync.transformers import parse_utc
from app.services.sync.upserter import upsert_work_order

logger = structlog.get_logger(__name__)


async def sync_recent_work_orders(
    lookback_hours: int = 1,
    sc_client: ServiceChannelClient | None = None,
    max_pages: int = 200,
) -> dict[str, Any]:
    """Fetch work orders from SC, filter to recent ones, and upsert them.

    Args:
        lookback_hours: Only upsert work orders whose `UpdatedDate` is within
            this window. Records older than the cutoff are counted as
            `skipped` but not upserted.
        sc_client: Optional injected client for testing.
        max_pages: Hard cap on pagination — passed through to the SC client.

    Returns:
        Summary: {"fetched", "skipped", "upserted", "errors"}. Errors are
        recorded per-WO; one failure does not abort the batch.
    """
    client = sc_client or ServiceChannelClient()
    cutoff = datetime.now(UTC) - timedelta(hours=lookback_hours)

    logger.info(
        "work order sync starting",
        lookback_hours=lookback_hours,
        cutoff=cutoff.isoformat(),
    )

    summary: dict[str, Any] = {
        "fetched": 0,
        "skipped": 0,
        "upserted": 0,
        "errors": [],
    }

    async for payload in client.iter_work_orders(max_pages=max_pages):
        summary["fetched"] += 1

        updated = parse_utc(payload.get("UpdatedDate"))
        if updated is not None and updated < cutoff:
            summary["skipped"] += 1
            continue

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
        skipped=summary["skipped"],
        upserted=summary["upserted"],
        errors=len(summary["errors"]),
    )
    return summary
