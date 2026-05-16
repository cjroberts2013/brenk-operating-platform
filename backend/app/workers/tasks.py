"""Procrastinate task definitions.

These are the recurring background jobs that keep our database in sync with
ServiceChannel. Task bodies will be implemented in Week 2; for now we have
the structure and signatures.
"""

import structlog

from app.workers.app import procrastinate_app

logger = structlog.get_logger(__name__)


@procrastinate_app.task(name="sync_work_orders", queue="default")
async def sync_work_orders(lookback_hours: int = 1) -> dict:
    """Sync recently updated work orders from ServiceChannel.

    Args:
        lookback_hours: How far back to look for updates.

    Returns:
        Summary of the sync run.
    """
    logger.info("sync_work_orders task triggered", lookback_hours=lookback_hours)
    # TODO Week 2: implement
    return {"status": "not_implemented", "fetched": 0}


@procrastinate_app.task(name="sync_work_order_detail", queue="default")
async def sync_work_order_detail(sc_work_order_id: int) -> dict:
    """Sync the full detail (notes, attachments) for a single work order."""
    logger.info("sync_work_order_detail task triggered", sc_work_order_id=sc_work_order_id)
    # TODO Week 2: implement
    return {"status": "not_implemented"}


@procrastinate_app.task(name="sync_vendors", queue="default")
async def sync_vendors() -> dict:
    """Sync vendor / provider data from ServiceChannel."""
    logger.info("sync_vendors task triggered")
    # TODO Week 2: implement
    return {"status": "not_implemented"}
