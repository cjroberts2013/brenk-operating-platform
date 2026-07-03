"""Procrastinate task definitions.

These are the recurring background jobs that keep our database in sync
with ServiceChannel. Task bodies are thin wrappers — real logic lives in
`app.services.sync`.
"""

from datetime import UTC, datetime

import structlog

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.services.categorize import categorize_uncategorized
from app.services.deadline_digest import build_digest_email, fetch_digest_items
from app.services.email import send_email
from app.services.invoice_sync import process_event, process_pending_events
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


@procrastinate_app.periodic(cron="0 * * * *")
@procrastinate_app.task(name="scheduled_sync_work_orders", queue="default")
async def scheduled_sync_work_orders(timestamp: int) -> dict:
    """Periodic sync trigger — runs hourly at the top of the hour via
    Procrastinate's built-in scheduler.

    Daryl can hit "Sync now" on the Work Orders page if he needs a
    fresher read; the manual button calls `sync_work_orders` directly.

    Rationale for hourly: SC issues ~8 new WOs/day for Brenk, so a
    5-minute cadence was massive overkill — 288 polls/day to catch
    8 WOs. Hourly drops that to 24/day per environment, well below
    any SC throttle and friendly to monthly network-call budgets.
    Adjust here if Daryl's reaction time on new requests becomes a
    problem.

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


@procrastinate_app.periodic(cron="* * * * *")
@procrastinate_app.task(name="sweep_webhook_events", queue="default")
async def sweep_webhook_events(timestamp: int) -> dict:
    """Process any pending SC webhook events into invoice state.

    Runs every minute. The receiver stores raw events fast and returns
    200; this is where the real materialization happens (idempotent +
    out-of-order safe, in `app.services.invoice_sync`). At Brenk's
    volume a 1-minute cadence is ample; it also serves as the
    at-least-once safety net for anything the receiver couldn't enqueue.

    `timestamp` is the Procrastinate scheduled tick (used for logging).
    """
    settings = get_settings()
    async with AsyncSessionLocal() as session:
        counts = await process_pending_events(session, sc_env=settings.SC_ENVIRONMENT)
    return counts


@procrastinate_app.task(name="process_webhook_event", queue="default")
async def process_webhook_event(event_id: int) -> dict:
    """Process a single webhook event by id. Available for a future
    defer-on-receipt path and for manual reprocessing."""
    settings = get_settings()
    async with AsyncSessionLocal() as session:
        result = await process_event(session, event_id, sc_env=settings.SC_ENVIRONMENT)
    return {"event_id": event_id, "status": result}


@procrastinate_app.periodic(cron="15 * * * *")
@procrastinate_app.task(name="categorize_work_orders", queue="default")
async def categorize_work_orders(timestamp: int) -> dict:
    """Categorize any work orders missing a Brenk job category.

    Runs hourly (offset from the top-of-hour WO sync so new WOs are already
    in the DB). Idempotent and capped per run, so steady state (~8 new
    WOs/day) is a handful of cheap Flash-Lite text calls; most runs do
    nothing. No-ops without GEMINI_API_KEY.

    `timestamp` is the Procrastinate scheduled tick (used for logging).
    """
    logger.info("categorize_work_orders tick", timestamp=timestamp)
    async with AsyncSessionLocal() as session:
        return await categorize_uncategorized(session)


@procrastinate_app.periodic(cron="0 12 * * *")
@procrastinate_app.task(name="send_deadline_digest", queue="default")
async def send_deadline_digest(timestamp: int) -> dict:
    """Email Daryl the daily turnaround-deadline digest.

    Cron is UTC: 12:00 = 7am CDT / 6am CST — before Daryl's day starts
    either way. (Bump to "0 13 * * *" for 8am/7am if the winter hour is
    too early.) Sends only when at least one WO is overdue or due within
    the due-soon window; quiet mornings send nothing. Re-deferring the
    task manually just re-sends the current digest — that's the manual
    re-send you'd want, so there's no last-sent guard. Without
    RESEND_API_KEY, send_email logs and no-ops.

    `timestamp` is the Procrastinate scheduled tick (used for logging).
    """
    logger.info("send_deadline_digest tick", timestamp=timestamp)
    settings = get_settings()
    async with AsyncSessionLocal() as session:
        items = await fetch_digest_items(session)

    if not items:
        logger.info("deadline digest empty — not sending")
        return {"sent": False, "items": 0}

    subject, html, text = build_digest_email(items, datetime.now(UTC))
    sent = await send_email(
        subject=subject,
        html=html,
        text=text,
        to=settings.REMINDER_TO_EMAIL or settings.QUOTE_TO_EMAIL,
        from_email=settings.QUOTE_FROM_EMAIL,
    )
    counts = {
        "sent": sent,
        "items": len(items),
        "overdue": sum(1 for i in items if i.urgency == "overdue"),
        "due_soon": sum(1 for i in items if i.urgency == "due_soon"),
        "waiting_on_cubesmart": sum(1 for i in items if i.section == "waiting_on_cubesmart"),
    }
    logger.info("deadline digest processed", **counts)
    return counts


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
