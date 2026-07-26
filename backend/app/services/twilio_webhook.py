"""Twilio inbound-webhook signature verification.

Twilio signs every webhook request with header `X-Twilio-Signature`. The
signature is HMAC-SHA1, keyed with the account's auth token, over a string
built from:

  1. the full request URL Twilio was configured to call (scheme + host +
     path + any query string), then
  2. for each POST param, sorted alphabetically by key, the key immediately
     followed by its value, all concatenated onto the URL.

then base64-encoded. Verification must run against the SAME URL Twilio used
— behind a proxy the app's own `request.url` may be the internal http URL,
so the caller passes the configured public URL (settings.TWILIO_WEBHOOK_URL).

Ref: Twilio "Validating Signatures from Twilio". Mirrors the fail-closed,
constant-time style of `app/services/sc_webhook.py`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from collections.abc import Mapping


def build_signature_base(url: str, params: Mapping[str, str]) -> str:
    """Concatenate the URL with alphabetically-sorted key+value pairs."""
    base = url
    for key in sorted(params):
        base += key + params[key]
    return base


def verify_twilio_signature(
    *,
    url: str,
    params: Mapping[str, str],
    auth_token: str,
    signature: str | None,
) -> bool:
    """True iff `signature` is a valid Twilio signature for this request.

    Fails closed: a missing signature or empty auth token returns False.
    Constant-time comparison avoids timing leaks.
    """
    if not signature or not auth_token:
        return False
    base = build_signature_base(url, params)
    expected = base64.b64encode(
        hmac.new(auth_token.encode("utf-8"), base.encode("utf-8"), hashlib.sha1).digest()
    ).decode("ascii")
    return hmac.compare_digest(expected, signature)
