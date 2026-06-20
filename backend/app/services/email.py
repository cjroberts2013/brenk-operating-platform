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

import re

import httpx
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

_RESEND_ENDPOINT = "https://api.resend.com/emails"
_TIMEOUT_SECONDS = 15.0

# Loose email check — same approach as the storefront quote form. Good
# enough to reject obvious junk before we hand an address to Resend;
# true deliverability is proven by whether the reply lands, not by regex.
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(email: str | None) -> bool:
    """True if `email` is a plausibly-valid address (loose format check)."""
    return bool(email and _EMAIL_PATTERN.match(email.strip()))


async def send_email(
    *,
    subject: str,
    html: str,
    text: str | None = None,
    reply_to: str | None = None,
    to: str | list[str] | None = None,
    from_email: str | None = None,
    attachments: list[dict[str, str]] | None = None,
) -> bool:
    """Send one email via Resend.

    `to` defaults to the configured quote recipient (Daryl) for the
    storefront lead path; pass an explicit address (e.g. a vendor's) to
    send elsewhere. `from_email` overrides the sender (defaults to
    QUOTE_FROM_EMAIL); pass a different verified-domain address for other
    flows. `attachments` is Resend's shape: a list of
    `{"filename": str, "content": <base64 str>}`.

    Returns True on a 2xx from Resend, False otherwise (including when
    no API key is configured). Never raises — email is best-effort and
    callers have already persisted/logged the underlying record.

    Always pass `text` when you can: a plain-text alternative alongside
    the HTML measurably improves deliverability (HTML-only mail is a
    spam-filter signal).
    """
    settings = get_settings()

    if not settings.RESEND_API_KEY:
        logger.warning("email.skip_no_api_key", subject=subject)
        return False

    recipients = [to] if isinstance(to, str) else (to or [settings.QUOTE_TO_EMAIL])
    payload: dict[str, object] = {
        "from": from_email or settings.QUOTE_FROM_EMAIL,
        "to": recipients,
        "subject": subject,
        "html": html,
    }
    if text:
        payload["text"] = text
    if reply_to:
        payload["reply_to"] = reply_to
    if attachments:
        payload["attachments"] = attachments

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

    logger.info("email.sent", subject=subject, to=recipients)
    return True
