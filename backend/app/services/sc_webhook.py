"""ServiceChannel webhook signature verification.

SC signs every webhook delivery: header `Sign-Type: HMACSHA256`, header
`Sign-Data: <base64>`. The signature is HMAC-SHA256 over the EXACT raw
request body bytes, keyed with the signing key (as text), base64-encoded.

Verification must run over the bytes received on the wire, never over
re-serialized JSON (key ordering / whitespace would break the HMAC).
See docs/architecture/sc-invoice-webhook-sync.md §5.1.
"""

import base64
import hashlib
import hmac


def verify_signature(raw_body: bytes, sign_data: str | None, key: str) -> bool:
    """True iff `sign_data` is a valid HMAC-SHA256 signature of `raw_body`.

    Fails closed: a missing signature or an empty key returns False.
    Uses a constant-time comparison to avoid timing leaks.
    """
    if not sign_data or not key:
        return False
    expected = base64.b64encode(
        hmac.new(key.encode("utf-8"), raw_body, hashlib.sha256).digest()
    ).decode("ascii")
    return hmac.compare_digest(expected, sign_data)
