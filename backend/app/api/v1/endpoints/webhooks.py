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

import structlog
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_async_db
from app.models.invoice import WebhookEvent
from app.services.sc_webhook import verify_signature

logger = structlog.get_logger(__name__)

router = APIRouter()


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
