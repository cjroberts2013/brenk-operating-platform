"""Gemini-backed work-order categorization.

Classifies a work order into one Brenk job type (the shared `job_types`
taxonomy) from its description's problem line — token-conscious: a tiny
text-only prompt, structured output (a type enum + confidence), Flash Lite.

No SDK — one httpx POST to the Generative Language API, mirroring the
Resend pattern in app/services/email.py. Returns None on any failure or
when GEMINI_API_KEY is unset, so callers (the batch task) degrade
gracefully and never block on the AI.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models.work_order import WorkOrder
from app.services.job_types import list_job_types
from app.services.vendor_message import problem_summary

logger = structlog.get_logger(__name__)

# Safety cap on how many WOs one batch run will categorize, so a bug or a
# big backfill can't burn an unbounded number of tokens in a single pass.
DEFAULT_BATCH_LIMIT = 50

_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
_TIMEOUT_SECONDS = 20.0


def _build_instructions(job_type_defs: list[tuple[str, str]]) -> str:
    return (
        "You categorize commercial facility-maintenance work orders into exactly "
        "one job type for a general contractor. Choose the single best type "
        "from the list based mainly on the work described. A suggested trade may be "
        "given but is often wrong — rely on the description. Job types:\n"
        + "\n".join(f"- {name}: {desc}" for name, desc in job_type_defs)
    )


def _build_schema(names: list[str]) -> dict:
    """Structured-output schema constraining the model to a valid job type +
    a 0..1 confidence, so the response is a tiny, parse-safe JSON object."""
    return {
        "type": "OBJECT",
        "properties": {
            "category": {"type": "STRING", "enum": names},
            "confidence": {"type": "NUMBER"},
        },
        "required": ["category", "confidence"],
        "propertyOrdering": ["category", "confidence"],
    }


async def categorize(
    description: str | None,
    trade_hint: str | None = None,
    *,
    job_type_defs: list[tuple[str, str]],
) -> tuple[str, float] | None:
    """Return (job_type, confidence) for a WO, or None if it can't be done.

    `job_type_defs` is the (name, description) taxonomy to classify into —
    loaded from the DB by the caller so the list stays editable. `description`
    is the raw SC description; we send only its problem line (last "/"-segment).
    None when there's no usable text, no API key, or the call/parse fails.
    """
    settings = get_settings()
    if not settings.GEMINI_API_KEY:
        logger.warning("categorize.skip_no_api_key")
        return None

    problem = problem_summary(description)
    if not problem or problem == "(none provided)":
        return None

    names = [name for name, _ in job_type_defs]
    if not names:
        return None

    prompt = _build_instructions(job_type_defs) + "\n\nWork order:\n"
    if trade_hint:
        prompt += f"Suggested trade (may be wrong): {trade_hint}\n"
    prompt += f"Description: {problem}"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 1024,
            "responseMimeType": "application/json",
            "responseSchema": _build_schema(names),
        },
    }
    url = f"{_API_BASE}/models/{settings.GEMINI_MODEL}:generateContent"

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.post(
                url,
                json=payload,
                headers={"x-goog-api-key": settings.GEMINI_API_KEY},
            )
    except httpx.HTTPError as exc:
        logger.error("categorize.request_failed", error=str(exc))
        return None

    if response.status_code >= 400:
        logger.error("categorize.rejected", status=response.status_code, body=response.text[:300])
        return None

    return _parse(response.json(), valid_names=set(names))


def _parse(body: dict, valid_names: set[str]) -> tuple[str, float] | None:
    """Pull (job_type, confidence) out of a generateContent response."""
    try:
        text = body["candidates"][0]["content"]["parts"][0]["text"]
        data = json.loads(text)
        category = data["category"]
        confidence = float(data.get("confidence", 0.0))
    except (KeyError, IndexError, ValueError, TypeError) as exc:
        logger.error("categorize.parse_failed", error=str(exc), body=str(body)[:300])
        return None

    if category not in valid_names:
        logger.warning("categorize.invalid_category", category=category)
        return None

    return category, max(0.0, min(1.0, confidence))


async def categorize_uncategorized(
    session: AsyncSession, limit: int = DEFAULT_BATCH_LIMIT
) -> dict[str, int]:
    """Categorize up to `limit` work orders that don't yet have a category.

    Idempotent: only touches WOs with `brenk_category IS NULL`. Each result
    is stored with source='ai' (the operator confirms/overrides later) plus
    the original guess in `brenk_category_ai`. No-ops without an API key.
    Caller need not commit — this commits once at the end.
    """
    if not get_settings().GEMINI_API_KEY:
        logger.warning("categorize_uncategorized.skip_no_api_key")
        return {"scanned": 0, "categorized": 0, "skipped": 0}

    # Load the editable taxonomy once and classify everyone against it.
    job_types = await list_job_types(session)
    job_type_defs = [(jt.name, jt.description or "") for jt in job_types]
    if not job_type_defs:
        logger.warning("categorize_uncategorized.no_job_types")
        return {"scanned": 0, "categorized": 0, "skipped": 0}

    rows = (
        (
            await session.execute(
                select(WorkOrder)
                .options(selectinload(WorkOrder.trade))
                .where(
                    WorkOrder.brenk_category.is_(None),
                    WorkOrder.description.is_not(None),
                )
                .order_by(WorkOrder.sc_work_order_id.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )

    categorized = 0
    for wo in rows:
        trade_hint = wo.trade.name if wo.trade else None
        result = await categorize(
            wo.description, trade_hint=trade_hint, job_type_defs=job_type_defs
        )
        if result is None:
            continue
        category, confidence = result
        wo.brenk_category = category
        wo.brenk_category_ai = category
        wo.brenk_category_source = "ai"
        wo.brenk_category_confidence = Decimal(str(round(confidence, 3)))
        wo.brenk_category_at = datetime.now(UTC)
        categorized += 1

    if categorized:
        await session.commit()
    return {"scanned": len(rows), "categorized": categorized, "skipped": len(rows) - categorized}
