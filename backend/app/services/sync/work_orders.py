"""Work order sync orchestration.

Glues the ServiceChannel client to the upserter. Each WO is committed in its
own transaction so a single malformed payload doesn't poison the batch.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from app.db.session import AsyncSessionLocal
from app.services.servicechannel.client import ServiceChannelClient
from app.services.sync.upserter import upsert_work_order

logger = structlog.get_logger(__name__)


async def sync_recent_work_orders(
    lookback_hours: int = 1,
    sc_client: ServiceChannelClient | None = None,
) -> dict[str, Any]:
    """Fetch recently-updated work orders from SC and upsert them.

    Args:
        lookback_hours: How far back to fetch updated work orders.
        sc_client: Optional injected client for testing. A fresh
            ServiceChannelClient is constructed if not provided.

    Returns:
        A summary dict: {"fetched": int, "upserted": int, "errors": list}.
        Errors are recorded per-WO; a failure on one does not abort the batch.
    """
    client = sc_client or ServiceChannelClient()
    since = (datetime.now(UTC) - timedelta(hours=lookback_hours)).isoformat()

    logger.info("work order sync starting", lookback_hours=lookback_hours, since=since)
    payloads = await client.list_work_orders(updated_since=since)

    summary: dict[str, Any] = {
        "fetched": len(payloads),
        "upserted": 0,
        "errors": [],
    }

    for payload in payloads:
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
