"""Procrastinate task definitions.

These are the recurring background jobs that keep our database in sync with
ServiceChannel. Task bodies are thin wrappers — real logic lives in
`app.services.sync`.
"""

import structlog

from app.services.sync.work_orders import sync_recent_work_orders
from app.workers.app import procrastinate_app

logger = structlog.get_logger(__name__)


@procrastinate_app.task(name="sync_work_orders", queue="default")
async def sync_work_orders(lookback_hours: int = 1) -> dict:
    """Sync recently updated work orders from ServiceChannel."""
    logger.info("sync_work_orders task triggered", lookback_hours=lookback_hours)
    return await sync_recent_work_orders(lookback_hours=lookback_hours)


@procrastinate_app.task(name="sync_work_order_detail", queue="default")
async def sync_work_order_detail(sc_work_order_id: int) -> dict:
    """Sync the full detail (notes, attachments) for a single work order.

    TODO: implement once we settle the notes-sync strategy. For now this is a
    placeholder so the task is registered with the scheduler.
    """
    logger.info("sync_work_order_detail task triggered", sc_work_order_id=sc_work_order_id)
    return {"status": "not_implemented", "sc_work_order_id": sc_work_order_id}


@procrastinate_app.task(name="sync_vendors", queue="default")
async def sync_vendors() -> dict:
    """Sync vendor / provider data from ServiceChannel.

    TODO: implement once Brenk's sub-vendor model is finalized. The SC
    `Provider` field references Brenk itself, not the sub-vendors Brenk
    dispatches to, so vendor data may need a different source.
    """
    logger.info("sync_vendors task triggered")
    return {"status": "not_implemented"}
