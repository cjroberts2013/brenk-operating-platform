"""Procrastinate task definitions.

These are the recurring background jobs that keep our database in sync with
ServiceChannel. Task bodies are thin wrappers — real logic lives in
`app.services.sync`.
"""

import structlog

from app.core.config import get_settings
from app.services.sync.work_orders import sync_recent_work_orders
from app.workers.app import procrastinate_app

logger = structlog.get_logger(__name__)
_settings = get_settings()


@procrastinate_app.task(name="sync_work_orders", queue="default")
async def sync_work_orders(lookback_hours: int = 1) -> dict:
    """Sync recently updated work orders from ServiceChannel.

    Manual / on-demand task. The recurring schedule lives on
    `scheduled_sync_work_orders` below — keep this signature parameterized
    so it can be deferred ad-hoc with a custom lookback (e.g., for
    backfill).
    """
    logger.info("sync_work_orders task triggered", lookback_hours=lookback_hours)
    return await sync_recent_work_orders(lookback_hours=lookback_hours)


@procrastinate_app.periodic(cron="*/5 * * * *")
@procrastinate_app.task(name="scheduled_sync_work_orders", queue="default")
async def scheduled_sync_work_orders(timestamp: int) -> dict:
    """Periodic sync trigger — runs every 5 minutes via Procrastinate's
    built-in scheduler.

    The `timestamp` arg is passed by Procrastinate (Unix epoch of the
    scheduled tick) and is used here only for logging. Sync work delegates
    to `sync_recent_work_orders` with the lookback from settings.
    """
    logger.info("scheduled sync tick", timestamp=timestamp)
    return await sync_recent_work_orders(
        lookback_hours=_settings.SC_SYNC_LOOKBACK_HOURS,
    )


@procrastinate_app.task(name="sync_work_order_detail", queue="default")
async def sync_work_order_detail(sc_work_order_id: int) -> dict:
    """Sync the full detail (notes, attachments) for a single work order.

    TODO: implement once we settle the notes-sync strategy.
    """
    logger.info("sync_work_order_detail task triggered", sc_work_order_id=sc_work_order_id)
    return {"status": "not_implemented", "sc_work_order_id": sc_work_order_id}


@procrastinate_app.task(name="sync_vendors", queue="default")
async def sync_vendors() -> dict:
    """Sync vendor / provider data from ServiceChannel.

    TODO: implement once Brenk's sub-vendor model is finalized.
    """
    logger.info("sync_vendors task triggered")
    return {"status": "not_implemented"}
