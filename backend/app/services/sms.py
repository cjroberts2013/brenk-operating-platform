"""Outbound SMS/MMS via Twilio.

A thin async wrapper around Twilio's Messages API, mirroring the design of
`app/services/email.py` (Resend):

- No SDK — the API is one form-encoded POST and we already depend on httpx.
- If the Twilio credentials are unset, `send_sms` logs a warning and returns
  False instead of raising, so local dev without a Twilio account degrades
  gracefully (the endpoint turns that into a "not configured" error).
- MMS photos ride along as `MediaUrl` params. Twilio fetches each URL
  itself, so they must be publicly reachable — ServiceChannel's presigned
  Azure SAS attachment links qualify (short-lived, but Twilio fetches at
  send time). Callers should only pass URLs they have verified fetchable.
"""

from __future__ import annotations

import re

import httpx
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

_TIMEOUT_SECONDS = 15.0

# Twilio caps MMS at 10 media per message (US/Canada).
MAX_MMS_MEDIA = 10
# Carriers cap total MMS media size at 5 MB; stay under so a big photo set
# degrades to fewer photos rather than an undeliverable message.
MAX_MMS_TOTAL_BYTES = 4_500_000
# Image types US carriers accept natively (others get rejected or dropped).
MMS_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/gif"}

_NON_DIGITS = re.compile(r"[^\d+]")


def normalize_phone(raw: str | None) -> str | None:
    """Normalize a stored phone number to E.164, or None if it can't be.

    Vendor phones were hand-entered ("(512) 555-1212", "512.555.1212",
    "+15125551212"...). US-centric: 10 digits get +1, 11 digits with a
    leading 1 get +. Anything else only passes if it already carries a
    plausible international +prefix.
    """
    if not raw:
        return None
    cleaned = _NON_DIGITS.sub("", raw.strip())
    if not cleaned:
        return None
    plus = cleaned.startswith("+")
    digits = cleaned.lstrip("+")
    if not digits.isdigit():
        return None
    if len(digits) == 10 and not plus:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    if plus and 8 <= len(digits) <= 15:
        return f"+{digits}"
    return None


async def send_sms(
    *,
    to: str,
    body: str,
    media_urls: list[str] | None = None,
) -> bool:
    """Send one SMS (or MMS, when `media_urls` is non-empty) via Twilio.

    `to` must already be E.164 (run it through `normalize_phone`). Returns
    True when Twilio accepts the message (2xx), False otherwise — including
    when no credentials are configured. Never raises; texting is
    best-effort and callers decide how to surface a failure.

    Note: a 2xx means Twilio *queued* the message, not that the handset
    received it. Delivery failures (bad number, carrier filtering) surface
    later in the Twilio console/logs.
    """
    settings = get_settings()

    if not (settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN):
        logger.warning("sms.skip_no_credentials", to=to)
        return False
    if not settings.TWILIO_FROM_NUMBER:
        logger.warning("sms.skip_no_from_number", to=to)
        return False

    data: dict[str, str | list[str]] = {
        "To": to,
        "From": settings.TWILIO_FROM_NUMBER,
        "Body": body,
    }
    if media_urls:
        # A list value encodes as a repeated MediaUrl form field.
        data["MediaUrl"] = media_urls[:MAX_MMS_MEDIA]

    endpoint = (
        f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"
    )
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.post(
                endpoint,
                data=data,
                auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
            )
    except httpx.HTTPError as exc:
        logger.error("sms.send_failed", error=str(exc), to=to)
        return False

    if response.status_code >= 400:
        logger.error(
            "sms.send_rejected",
            status=response.status_code,
            body=response.text[:300],
            to=to,
        )
        return False

    logger.info("sms.sent", to=to, media_count=len(media_urls or []))
    return True
