"""Unit tests for SC webhook signature verification (no DB)."""

import base64
import hashlib
import hmac

from app.services.sc_webhook import verify_signature

KEY = "brenk-webhook-test-key"


def _sign(body: bytes, key: str = KEY) -> str:
    return base64.b64encode(hmac.new(key.encode(), body, hashlib.sha256).digest()).decode()


def test_valid_signature_passes() -> None:
    body = b'{"EventType":"InvoicePaid","Object":{"Id":42}}'
    assert verify_signature(body, _sign(body), KEY) is True


def test_one_byte_body_mutation_fails() -> None:
    body = b'{"EventType":"InvoicePaid","Object":{"Id":42}}'
    sig = _sign(body)
    assert verify_signature(body + b" ", sig, KEY) is False


def test_wrong_key_fails() -> None:
    body = b'{"EventType":"InvoiceVoided"}'
    assert verify_signature(body, _sign(body, "other-key"), KEY) is False


def test_fails_closed_on_missing_sig_or_empty_key() -> None:
    body = b"{}"
    assert verify_signature(body, None, KEY) is False
    assert verify_signature(body, "", KEY) is False
    assert verify_signature(body, _sign(body), "") is False
