"""Outbound email via Resend.

A thin async wrapper around Resend's HTTP API (https://resend.com).
Used by the storefront "Request a Quote" form to email Daryl.

Design notes:
- No SDK — Resend's API is one POST, and we already depend on httpx.
- If `RESEND_API_KEY` is unset, `send_email` logs a warning and returns
  False instead of raising. Callers are expected to have already logged
  the underlying lead, so a missing key degrades gracefully (the form
  still "works" in local dev) without losing data.
"""

from __future__ import annotations

import httpx
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

_RESEND_ENDPOINT = "https://api.resend.com/emails"
_TIMEOUT_SECONDS = 15.0


async def send_email(
    *,
    subject: str,
    html: str,
    text: str | None = None,
    reply_to: str | None = None,
) -> bool:
    """Send one email to the configured recipient via Resend.

    Returns True on a 2xx from Resend, False otherwise (including when
    no API key is configured). Never raises — email is best-effort here
    and the caller has already persisted/logged the lead.

    Always pass `text` when you can: a plain-text alternative alongside
    the HTML measurably improves deliverability (HTML-only mail is a
    spam-filter signal).
    """
    settings = get_settings()

    if not settings.RESEND_API_KEY:
        logger.warning("email.skip_no_api_key", subject=subject)
        return False

    payload: dict[str, object] = {
        "from": settings.QUOTE_FROM_EMAIL,
        "to": [settings.QUOTE_TO_EMAIL],
        "subject": subject,
        "html": html,
    }
    if text:
        payload["text"] = text
    if reply_to:
        payload["reply_to"] = reply_to

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.post(
                _RESEND_ENDPOINT,
                json=payload,
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            )
    except httpx.HTTPError as exc:
        logger.error("email.send_failed", error=str(exc), subject=subject)
        return False

    if response.status_code >= 400:
        logger.error(
            "email.send_rejected",
            status=response.status_code,
            body=response.text[:300],
            subject=subject,
        )
        return False

    logger.info("email.sent", subject=subject, to=settings.QUOTE_TO_EMAIL)
    return True
