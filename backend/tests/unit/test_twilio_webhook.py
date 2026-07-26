"""Unit tests for Twilio inbound-webhook signature verification.

Anchored two ways: (1) an exact assertion on the signature base string,
which is the Twilio-specific logic — the full URL followed by
alphabetically-sorted key+value pairs, per Twilio's "Validating
Signatures" spec; (2) a round-trip signed with an INDEPENDENT, explicit
HMAC-SHA1 implementation, so a regression in the hash choice or param
sorting is caught (not just self-consistency).
"""

import base64
import hashlib
import hmac

from app.services.twilio_webhook import build_signature_base, verify_twilio_signature

_URL = "https://mycompany.com/myapp.php?foo=1&bar=2"
_PARAMS = {
    "Digits": "1234",
    "To": "+18005551212",
    "From": "+14158675310",
    "Caller": "+14158675310",
    "CallSid": "CA1234567890ABCDE",
}
_AUTH_TOKEN = "12345678901234567890123456789012"


def _sign(url: str, params: dict[str, str], token: str) -> str:
    """Independent reference impl of Twilio's algorithm (HMAC-SHA1)."""
    base = url
    for key in sorted(params):
        base += key + params[key]
    return base64.b64encode(hmac.new(token.encode(), base.encode(), hashlib.sha1).digest()).decode()


def test_build_signature_base_is_url_then_sorted_pairs() -> None:
    # Exactly Twilio's spec: URL, then each key immediately followed by its
    # value, in alphabetical key order.
    base = build_signature_base(_URL, {"b": "2", "a": "1", "C": "3"})
    assert base == _URL + "C3" + "a1" + "b2"  # case-sensitive Unix sort


def test_verify_accepts_correct_signature() -> None:
    sig = _sign(_URL, _PARAMS, _AUTH_TOKEN)
    assert verify_twilio_signature(url=_URL, params=_PARAMS, auth_token=_AUTH_TOKEN, signature=sig)


def test_verify_rejects_tampered_signature() -> None:
    assert not verify_twilio_signature(
        url=_URL, params=_PARAMS, auth_token=_AUTH_TOKEN, signature="wrongsig"
    )


def test_verify_rejects_tampered_params() -> None:
    sig = _sign(_URL, _PARAMS, _AUTH_TOKEN)
    tampered = dict(_PARAMS, Digits="9999")
    assert not verify_twilio_signature(
        url=_URL, params=tampered, auth_token=_AUTH_TOKEN, signature=sig
    )


def test_verify_rejects_wrong_token() -> None:
    sig = _sign(_URL, _PARAMS, _AUTH_TOKEN)
    assert not verify_twilio_signature(
        url=_URL, params=_PARAMS, auth_token="different-token", signature=sig
    )


def test_verify_fails_closed_on_missing_signature_or_token() -> None:
    sig = _sign(_URL, _PARAMS, _AUTH_TOKEN)
    assert not verify_twilio_signature(
        url=_URL, params=_PARAMS, auth_token=_AUTH_TOKEN, signature=None
    )
    assert not verify_twilio_signature(url=_URL, params=_PARAMS, auth_token="", signature=sig)
