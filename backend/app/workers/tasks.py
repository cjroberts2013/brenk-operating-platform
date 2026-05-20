"""Procrastinate task definitions.

These are the recurring background jobs that keep our database in sync
with ServiceChannel. Task bodies are thin wrappers — real logic lives in
`app.services.sync`.
"""

import structlog

from app.db.session import AsyncSessionLocal
from app.services.servicechannel.client import ServiceChannelClient
from app.services.sync.notes import sync_notes_for_sc_work_order_id
from app.services.sync.vendors import sync_vendors_from_sc
from app.services.sync.work_orders import sync_all_work_orders
from app.workers.app import procrastinate_app

logger = structlog.get_logger(__name__)


@procrastinate_app.task(name="sync_work_orders", queue="default")
async def sync_work_orders() -> dict:
    """Manual / on-demand sync trigger. Identical to the scheduled run."""
    logger.info("sync_work_orders task triggered")
    return await sync_all_work_orders()


@procrastinate_app.periodic(cron="*/5 * * * *")
@procrastinate_app.task(name="scheduled_sync_work_orders", queue="default")
async def scheduled_sync_work_orders(timestamp: int) -> dict:
    """Periodic sync trigger — runs every 5 minutes via Procrastinate's
    built-in scheduler.

    The `timestamp` arg is passed by Procrastinate (Unix epoch of the
    scheduled tick) and is used here only for logging.
    """
    logger.info("scheduled sync tick", timestamp=timestamp)
    return await sync_all_work_orders()


@procrastinate_app.task(name="sync_work_order_detail", queue="default")
async def sync_work_order_detail(sc_work_order_id: int) -> dict:
    """Force-resync the notes thread for a single work order.

    The WO must already exist locally (run a WO sync first). Use this
    task to refresh notes on demand, independent of the count-delta
    trigger in the periodic sync.

    TODO: extend to attachments once SC exposes a working endpoint.
    """
    logger.info("sync_work_order_detail task triggered", sc_work_order_id=sc_work_order_id)
    client = ServiceChannelClient()
    async with AsyncSessionLocal() as session:
        count = await sync_notes_for_sc_work_order_id(session, client, sc_work_order_id)
        await session.commit()
    return {"sc_work_order_id": sc_work_order_id, "notes_synced": count}


@procrastinate_app.task(name="sync_vendors", queue="default")
async def sync_vendors() -> dict:
    """Sync the vendor list from ServiceChannel's user catalog.

    SC users are the canonical identity for Brenk's sub-vendors (each
    is added to SC under an `admin+N@brenkfacilityservices.com` email).
    This task imports them all and the operator curates the rest in
    the dashboard. Brenk-internal fields are never overwritten.
    """
    logger.info("sync_vendors task triggered")
    return await sync_vendors_from_sc()
