"""ServiceChannel webhook receiver.

`POST /api/v1/webhooks/servicechannel` — mounted on the PUBLIC router (no
Supabase JWT). Authenticity is established by the HMAC signature, not a
bearer token.

Contract (docs/architecture/sc-invoice-webhook-sync.md §5):
  - Do only: verify signature over raw bytes, store the raw event, ack.
    No business logic in the request path. SC needs a 2xx within 5 s.
  - The raw body is the only copy we will ever get (the read API is
    blocked), so persist exact bytes before any parsing.
  - Idempotent: `dedupe_key = sha256(raw_body)` + ON CONFLICT DO NOTHING,
    so SC's byte-identical retries are a clean no-op.
  - Always 200 once the row is stored, even for unknown EventType. The
    worker decides what to do; the HTTP layer never errors on content
    (a non-2xx loop would trip SC's webhook-disable circuit breaker).

Processing (the Procrastinate worker + work_orders integration) is wired
in the next slice; rows land here as `status='pending'`.
"""

import hashlib
import json
from typing import Annotated
from urllib.parse import parse_qsl

import structlog
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.db.session import get_async_db
from app.models.invoice import WebhookEvent
from app.models.work_order import SmsReply, Vendor, WorkOrder, WoVendorAssignment
from app.services.sc_webhook import verify_signature
from app.services.sms import normalize_phone, send_sms
from app.services.sms_inbound import (
    compose_opt_out_alert,
    compose_reply_forward,
    is_opt_out,
)
from app.services.twilio_webhook import verify_twilio_signature

logger = structlog.get_logger(__name__)

router = APIRouter()

# Empty TwiML — tells Twilio "received, don't auto-reply to the sender".
_TWIML_EMPTY = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


def _ack() -> Response:
    # Fresh Response per call (Response objects are single-use in Starlette).
    return Response(content='{"received": true}', media_type="application/json", status_code=200)


@router.api_route("/servicechannel", methods=["GET", "HEAD"])
async def webhook_reachability() -> Response:
    """Some SC reachability checks use GET/HEAD. Always 200."""
    return _ack()


@router.post("/servicechannel")
async def receive_sc_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> Response:
    settings = get_settings()
    raw = await request.body()
    sign_data = request.headers.get("Sign-Data")

    # Empty body = the UI "Ping URL" connectivity test (often unsigned).
    # Ack so the ping succeeds; store nothing.
    if not raw.strip():
        logger.info("sc_webhook_ping")
        return _ack()

    valid = verify_signature(raw, sign_data, settings.SC_WEBHOOK_SIGNING_KEY)

    # Best-effort parse for indexable fields. Never let parsing fail the
    # request — the raw bytes are what matter; the worker re-parses.
    event_type: str | None = None
    object_id: int | None = None
    try:
        body = json.loads(raw)
        if isinstance(body, dict):
            event_type = body.get("EventType")
            obj = body.get("Object")
            if isinstance(obj, dict) and isinstance(obj.get("Id"), int):
                object_id = obj["Id"]
    except (json.JSONDecodeError, ValueError):
        pass

    if not valid:
        # Not a legitimate SC delivery (or wrong/missing key). Record it
        # for audit and reject — invalid signatures are not SC retries, so
        # a 401 here doesn't risk the circuit breaker.
        await db.execute(
            pg_insert(WebhookEvent).values(
                sc_env=settings.SC_ENVIRONMENT,
                raw_body=raw,
                sign_data=sign_data,
                signature_valid=False,
                event_type=event_type,
                object_id=object_id,
                status="invalid_signature",
            )
        )
        await db.commit()
        logger.warning(
            "sc_webhook_invalid_signature",
            event_type=event_type,
            object_id=object_id,
        )
        return Response(
            content='{"error": "invalid signature"}',
            media_type="application/json",
            status_code=401,
        )

    dedupe_key = hashlib.sha256(raw).hexdigest()
    result = await db.execute(
        pg_insert(WebhookEvent)
        .values(
            sc_env=settings.SC_ENVIRONMENT,
            raw_body=raw,
            sign_data=sign_data,
            signature_valid=True,
            event_type=event_type,
            object_id=object_id,
            dedupe_key=dedupe_key,
            status="pending",
        )
        .on_conflict_do_nothing(index_elements=["dedupe_key"])
    )
    await db.commit()
    dedupe_hit = result.rowcount == 0
    logger.info(
        "sc_webhook_received",
        event_type=event_type,
        object_id=object_id,
        signature_valid=True,
        dedupe_hit=dedupe_hit,
    )
    # NOTE: the Procrastinate defer of process_webhook_event(id) is wired
    # in the next slice; the periodic sweep also picks up pending rows.
    return _ack()


# --------------------------------------------------------------------------- #
# Twilio inbound SMS — vendor replies to our toll-free number
# --------------------------------------------------------------------------- #


def _twiml() -> Response:
    return Response(content=_TWIML_EMPTY, media_type="application/xml", status_code=200)


async def _match_vendor(db: AsyncSession, from_number: str) -> Vendor | None:
    """Find the vendor whose phone matches the inbound number (E.164 compare).

    Vendor phones are hand-entered in varied formats, so we normalize both
    sides in Python. At ~20 active vendors this one small query is cheap.
    """
    normalized_from = normalize_phone(from_number)
    if normalized_from is None:
        return None
    vendors = (await db.execute(select(Vendor).where(Vendor.phone.is_not(None)))).scalars().all()
    for v in vendors:
        if normalize_phone(v.phone) == normalized_from:
            return v
    return None


async def _recent_notified_wo(db: AsyncSession, vendor_id: int):
    """The vendor's most recently-notified work order — best-effort context
    for "which job is this reply about". Returns (wo_number, location) or
    (None, None)."""
    stmt = (
        select(WorkOrder)
        .join(WoVendorAssignment, WoVendorAssignment.work_order_id == WorkOrder.id)
        .options(selectinload(WorkOrder.location))
        .where(WoVendorAssignment.vendor_id == vendor_id)
        .where(WoVendorAssignment.notified_at.is_not(None))
        .order_by(WoVendorAssignment.notified_at.desc())
        .limit(1)
    )
    wo = (await db.execute(stmt)).scalar_one_or_none()
    if wo is None:
        return None, None
    loc = wo.location
    location = None
    if loc is not None:
        location = " ".join(p for p in [loc.store_id, loc.name] if p) or None
    return wo.sc_number, location


@router.post("/twilio")
async def receive_twilio_sms(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> Response:
    """Inbound vendor SMS reply. Verify Twilio's signature, log the reply
    (history), and forward it to VENDOR_REPLY_TO_PHONE — a distinct alert if
    it's an opt-out (STOP). Text-only; media is noted, not relayed.

    Always returns empty TwiML so Twilio never auto-replies to the vendor.
    403 on a bad/missing signature.
    """
    settings = get_settings()
    # Twilio posts application/x-www-form-urlencoded. Parse the raw body
    # directly (avoids a python-multipart dependency); parse_qsl decodes the
    # values, matching what Twilio signed over.
    raw = await request.body()
    params = dict(parse_qsl(raw.decode("utf-8"), keep_blank_values=True))

    # Validate against the exact URL Twilio was configured with (behind Fly's
    # proxy `request.url` is the internal http URL, which wouldn't match).
    url = settings.TWILIO_WEBHOOK_URL or str(request.url)
    signature = request.headers.get("X-Twilio-Signature")
    if not verify_twilio_signature(
        url=url,
        params=params,
        auth_token=settings.TWILIO_AUTH_TOKEN,
        signature=signature,
    ):
        logger.warning("twilio_webhook_invalid_signature", from_number=params.get("From"))
        return Response(content="invalid signature", status_code=403)

    from_number = params.get("From", "")
    body = params.get("Body", "")
    message_sid = params.get("MessageSid") or params.get("SmsSid")
    try:
        num_media = int(params.get("NumMedia", "0"))
    except ValueError:
        num_media = 0

    vendor = await _match_vendor(db, from_number)
    opt_out = is_opt_out(body)

    wo_number = location = None
    if vendor is not None and not opt_out:
        wo_number, location = await _recent_notified_wo(db, vendor.id)

    # Forward (best-effort) to the operator's phone.
    forwarded = False
    reply_to = normalize_phone(settings.VENDOR_REPLY_TO_PHONE)
    if reply_to is not None:
        if opt_out:
            text = compose_opt_out_alert(
                vendor_name=vendor.name if vendor else None, from_number=from_number
            )
        else:
            text = compose_reply_forward(
                vendor_name=vendor.name if vendor else None,
                from_number=from_number,
                body=body,
                wo_number=wo_number,
                location=location,
            )
        try:
            forwarded = await send_sms(to=reply_to, body=text)
        except Exception as exc:  # a failed forward must not fail the webhook
            logger.warning("twilio_reply_forward_failed", error=str(exc))

    # Log the reply (history). Idempotent on the Twilio MessageSid so a
    # Twilio retry doesn't double-insert.
    values = {
        "twilio_message_sid": message_sid,
        "from_number": from_number,
        "body": body or None,
        "num_media": num_media,
        "vendor_id": vendor.id if vendor else None,
        "is_opt_out": opt_out,
        "forwarded": forwarded,
    }
    if message_sid:
        await db.execute(
            pg_insert(SmsReply)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["twilio_message_sid"])
        )
    else:
        await db.execute(pg_insert(SmsReply).values(**values))
    await db.commit()

    logger.info(
        "twilio_sms_received",
        from_number=from_number,
        vendor_id=vendor.id if vendor else None,
        opt_out=opt_out,
        forwarded=forwarded,
        num_media=num_media,
    )
    return _twiml()
