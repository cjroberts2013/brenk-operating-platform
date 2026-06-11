"""Process stored SC invoice webhook events into materialized state.

Consumes pending `webhook_events` rows: parses each, routes on
`EventType`, upserts the `invoices` row (+ line items + status history),
and syncs the relevant fields onto `work_orders`. Idempotent and
out-of-order safe.

We cannot re-fetch invoices (the read API is blocked), so the stored raw
event is authoritative. Field names are mapped defensively with
fallbacks; confirm them against real SC *Event Objects* payloads before
go-live (see docs/architecture/sc-invoice-webhook-sync.md §5.2, §7, §11).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invoice import (
    Invoice,
    InvoiceLabor,
    InvoiceMaterial,
    InvoiceStatusHistory,
    WebhookEvent,
)
from app.models.work_order import WorkOrder

logger = structlog.get_logger(__name__)

# All invoice event types we materialize. Anything else is a no-op
# (WorkOrder*) or dead-lettered (unknown).
INVOICE_EVENT_TYPES = {
    "InvoiceCreated",
    "InvoiceOpen",
    "InvoiceApproved",
    "InvoiceOnHold",
    "InvoiceReviewed",
    "InvoiceRejected",
    "InvoiceApprovalCodeChanged",
    "InvoiceVoided",
    "InvoicePaid",
    "InvoiceDisputed",
    "InvoiceStarAdded",
    "InvoiceStarRemoved",
}

# EventType is authoritative for state transitions (a sample InvoiceVoided
# payload can still carry Status: "OPEN"). Events not listed here carry no
# status change of their own (e.g. star add/remove, approval-code change).
_EVENT_STATUS: dict[str, str] = {
    "InvoiceCreated": "Open",
    "InvoiceOpen": "Open",
    "InvoiceApproved": "Approved",
    "InvoiceOnHold": "On Hold",
    "InvoiceReviewed": "Reviewed",
    "InvoiceRejected": "Rejected",
    "InvoiceVoided": "Void",
    "InvoicePaid": "Paid",
    "InvoiceDisputed": "Disputed",
}


# --------------------------------------------------------------------------- #
# Small, forgiving extractors
# --------------------------------------------------------------------------- #
def _first(obj: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        v = obj.get(k)
        if v is not None and v != "":
            return v
    return None


def _first_str(obj: dict[str, Any], *keys: str) -> str | None:
    v = _first(obj, *keys)
    if v is None:
        return None
    if isinstance(v, dict):
        # e.g. ChangedBy: {"UserName": "..."}
        inner = _first(v, "UserName", "Name")
        return str(inner) if inner is not None else None
    return str(v)


def _as_int(v: Any) -> int | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _as_dec(v: Any) -> Decimal | None:
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _parse_dt(v: Any) -> datetime | None:
    if not v or not isinstance(v, str):
        return None
    try:
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


# --------------------------------------------------------------------------- #
# Public entry points
# --------------------------------------------------------------------------- #
async def process_pending_events(
    db: AsyncSession, *, sc_env: str, limit: int = 200
) -> dict[str, int]:
    """Process all pending webhook events (oldest first). Each is handled
    in its own transaction so one poison event can't block the rest."""
    ids = (
        await db.execute(
            select(WebhookEvent.id)
            .where(WebhookEvent.status == "pending")
            .order_by(WebhookEvent.id)
            .limit(limit)
        )
    ).scalars().all()
    counts = {"processed": 0, "dead_letter": 0, "skipped": 0}
    for event_id in ids:
        result = await process_event(db, event_id, sc_env=sc_env)
        counts[result] = counts.get(result, 0) + 1
    if any(counts.values()):
        logger.info("webhook_events_swept", **counts)
    return counts


async def process_event(db: AsyncSession, event_id: int, *, sc_env: str) -> str:
    """Process one event by id. Commits. Returns 'processed' | 'dead_letter'
    | 'skipped' (already handled / locked by another worker)."""
    event = (
        await db.execute(
            select(WebhookEvent)
            .where(WebhookEvent.id == event_id)
            .with_for_update(skip_locked=True)
        )
    ).scalar_one_or_none()
    if event is None or event.status != "pending":
        return "skipped"

    try:
        result = await _apply(db, event, sc_env=sc_env)
        event.status = result
        event.processed_at = datetime.now(UTC)
        await db.commit()
        return result
    except Exception as exc:
        await db.rollback()
        ev = await db.get(WebhookEvent, event_id)
        if ev is not None:
            ev.status = "dead_letter"
            ev.error = f"{type(exc).__name__}: {exc}"[:1000]
            ev.processed_at = datetime.now(UTC)
            await db.commit()
        logger.error("webhook_event_failed", event_id=event_id, error=str(exc))
        return "dead_letter"


# --------------------------------------------------------------------------- #
# Routing + application
# --------------------------------------------------------------------------- #
async def _apply(db: AsyncSession, event: WebhookEvent, *, sc_env: str) -> str:
    """Returns the status to stamp on the event. Raises only on unexpected
    errors (caller dead-letters those); known-bad payloads return
    'dead_letter' with a recorded reason."""
    body = json.loads(event.raw_body)
    if not isinstance(body, dict):
        event.error = "payload is not a JSON object"
        return "dead_letter"

    event_type = body.get("EventType")
    if not event_type:
        event.error = "missing EventType"
        return "dead_letter"

    if event_type not in INVOICE_EVENT_TYPES:
        # WorkOrder events are a documented future extension point; everything
        # else is genuinely unexpected.
        if str(event_type).startswith("WorkOrder"):
            return "processed"
        event.error = f"unhandled EventType {event_type}"
        return "dead_letter"

    obj = body.get("Object")
    if not isinstance(obj, dict):
        event.error = "invoice event missing Object"
        return "dead_letter"

    invoice_number = _first_str(obj, "Number", "InvoiceNumber")
    if not invoice_number:
        event.error = "invoice event missing invoice number"
        return "dead_letter"

    await _apply_invoice_event(db, event, sc_env, event_type, obj, invoice_number)
    return "processed"


async def _apply_invoice_event(
    db: AsyncSession,
    event: WebhookEvent,
    sc_env: str,
    event_type: str,
    obj: dict[str, Any],
    invoice_number: str,
) -> None:
    sc_invoice_id = _as_int(obj.get("Id"))
    wo_tracking = _as_int(
        _first(obj, "WoTrackingNumber", "TrackingNumber", "WorkOrderId")
    )
    ev_time = _parse_dt(_first(obj, "UpdatedDateDTO", "UpdatedDate")) or _parse_dt(
        _first(obj, "LastActionDateDTO", "LastActionDate")
    )
    status = _EVENT_STATUS.get(event_type) or _first_str(obj, "Status")

    # Locate the existing invoice: by sc_invoice_id first, else by the
    # (number, wo) key so a backfill row gets adopted.
    invoice: Invoice | None = None
    if sc_invoice_id is not None:
        invoice = (
            await db.execute(
                select(Invoice).where(
                    Invoice.sc_env == sc_env, Invoice.sc_invoice_id == sc_invoice_id
                )
            )
        ).scalar_one_or_none()
    if invoice is None:
        invoice = (
            await db.execute(
                select(Invoice).where(
                    Invoice.sc_env == sc_env,
                    Invoice.invoice_number == invoice_number,
                    Invoice.wo_tracking_number.is_(wo_tracking)
                    if wo_tracking is None
                    else Invoice.wo_tracking_number == wo_tracking,
                )
            )
        ).scalar_one_or_none()

    is_new = invoice is None
    if is_new:
        invoice = Invoice(
            sc_env=sc_env, invoice_number=invoice_number, source="webhook"
        )
        db.add(invoice)

    # Out-of-order guard: a stale (late) event must not regress newer state.
    stale = (
        not is_new
        and invoice.sc_updated_date is not None
        and ev_time is not None
        and invoice.sc_updated_date > ev_time
    )

    if not stale:
        # Scalar fields: only overwrite with present (non-None) values, so a
        # sparse status-change event doesn't null out fields a richer event
        # already populated.
        scalars: dict[str, Any] = {
            "sc_invoice_id": sc_invoice_id,
            "wo_tracking_number": wo_tracking,
            "subscriber_id": _as_int(_first(obj, "SubscriberId")),
            "provider_id": _as_int(_first(obj, "ProviderId")),
            "location_id": _as_int(_first(obj, "LocationId")),
            "status": status,
            "trade": _first_str(obj, "Trade", "TradeName"),
            "category": _first_str(obj, "Category", "CategoryName"),
            "description": _first_str(obj, "Description", "InvoiceText"),
            "currency": _first_str(obj, "Currency", "CurrencyCode"),
            "subtotal": _as_dec(_first(obj, "Subtotal", "InvoiceSubtotal")),
            "invoice_tax": _as_dec(_first(obj, "InvoiceTax", "Tax")),
            "invoice_total": _as_dec(_first(obj, "InvoiceTotal", "Total")),
            "approval_code": _first_str(obj, "ApprovalCode"),
            "batch_number": _first_str(obj, "BatchNumber"),
            "comments": _first_str(obj, "Comments"),
            "invoice_date": _parse_dt(_first(obj, "InvoiceDateDTO", "InvoiceDate")),
            "posted_date": _parse_dt(_first(obj, "PostedDateDTO", "PostedDate")),
            "approved_date": _parse_dt(_first(obj, "ApprovedDateDTO", "ApprovedDate")),
            "paid_date": _parse_dt(_first(obj, "PaidDateDTO", "PaidDate")),
            "last_action_date": _parse_dt(
                _first(obj, "LastActionDateDTO", "LastActionDate")
            ),
        }
        for col, val in scalars.items():
            if val is not None:
                setattr(invoice, col, val)
        invoice.source = "webhook"
        if ev_time is not None:
            invoice.sc_updated_date = ev_time

        # Line items: replace wholesale only when the array is present and
        # non-empty (empty arrays on status events must not wipe them).
        if sc_invoice_id is not None:
            await _replace_line_items(db, sc_env, sc_invoice_id, obj)

        await _sync_work_order(
            db, sc_env, event_type, obj, wo_tracking, sc_invoice_id,
            invoice_number, status, invoice.invoice_total, ev_time,
        )

    # Status history: always append (even for stale/late events) for audit.
    db.add(
        InvoiceStatusHistory(
            sc_env=sc_env,
            sc_invoice_id=sc_invoice_id if sc_invoice_id is not None else 0,
            event_type=event_type,
            status=status,
            changed_by=_first_str(obj, "StatusChangeUser", "ChangedByUserName", "ChangedBy"),
            event_time=ev_time,
            webhook_event_id=event.id,
        )
    )


async def _replace_line_items(
    db: AsyncSession, sc_env: str, sc_invoice_id: int, obj: dict[str, Any]
) -> None:
    labors = obj.get("Labors")
    if isinstance(labors, list) and labors:
        await db.execute(
            delete(InvoiceLabor).where(
                InvoiceLabor.sc_env == sc_env,
                InvoiceLabor.sc_invoice_id == sc_invoice_id,
            )
        )
        for line in labors:
            if not isinstance(line, dict):
                continue
            db.add(
                InvoiceLabor(
                    sc_env=sc_env,
                    sc_invoice_id=sc_invoice_id,
                    skill_level=_as_int(line.get("SkillLevel")),
                    labor_type=_as_int(line.get("LaborType")),
                    num_of_tech=_as_int(line.get("NumOfTech")),
                    hourly_rate=_as_dec(line.get("HourlyRate")),
                    hours=_as_dec(line.get("Hours")),
                    amount=_as_dec(line.get("Amount")),
                )
            )

    materials = obj.get("Materials")
    if isinstance(materials, list) and materials:
        await db.execute(
            delete(InvoiceMaterial).where(
                InvoiceMaterial.sc_env == sc_env,
                InvoiceMaterial.sc_invoice_id == sc_invoice_id,
            )
        )
        for line in materials:
            if not isinstance(line, dict):
                continue
            db.add(
                InvoiceMaterial(
                    sc_env=sc_env,
                    sc_invoice_id=sc_invoice_id,
                    description=_first_str(line, "Description"),
                    part_num=_first_str(line, "PartNum"),
                    unit_type=_as_int(line.get("UnitType")),
                    unit_price=_as_dec(line.get("UnitPrice")),
                    quantity=_as_dec(line.get("Quantity")),
                    amount=_as_dec(line.get("Amount")),
                )
            )


async def _sync_work_order(
    db: AsyncSession,
    sc_env: str,
    event_type: str,
    obj: dict[str, Any],
    wo_tracking: int | None,
    sc_invoice_id: int | None,
    invoice_number: str,
    status: str | None,
    invoice_total: Decimal | None,
    ev_time: datetime | None,
) -> None:
    """Mirror invoice state onto the matching work order, so the invoice
    queue derives Sent -> Approved -> Paid from SC."""
    if wo_tracking is None:
        return
    wo = (
        await db.execute(
            select(WorkOrder).where(WorkOrder.sc_work_order_id == wo_tracking)
        )
    ).scalar_one_or_none()
    if wo is None:
        return

    if sc_invoice_id is not None:
        wo.sc_invoice_id = sc_invoice_id
    wo.sc_invoice_number = invoice_number
    if status is not None:
        wo.sc_invoice_status = status
    if invoice_total is not None:
        wo.sc_invoice_total = invoice_total

    if event_type in ("InvoiceCreated", "InvoiceOpen") and wo.sc_invoice_submitted_at is None:
        wo.sc_invoice_submitted_at = (
            _parse_dt(_first(obj, "PostedDateDTO", "PostedDate")) or ev_time
        )

    if event_type == "InvoicePaid":
        paid = _parse_dt(_first(obj, "PaidDateDTO", "PaidDate")) or ev_time
        wo.sc_paid_at = paid
        # Populate the manual field too, when empty, so the existing Paid-tab
        # / dashboard logic reflects it without a query refactor. Operators
        # can still override brenk_paid_at by hand.
        if wo.brenk_paid_at is None and paid is not None:
            wo.brenk_paid_at = paid

    if event_type == "InvoiceRejected":
        wo.sc_invoice_last_error = _first_str(obj, "RejectionReason", "Comments")
