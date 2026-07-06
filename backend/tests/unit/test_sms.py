"""Tests for the Twilio SMS service (phone normalization + send)."""

from types import SimpleNamespace

import httpx
import pytest
import respx

import app.services.sms as sms_mod
from app.services.sms import normalize_phone, send_sms

TWILIO = "https://api.twilio.com/2010-04-01/Accounts/ACtest/Messages.json"


def _fake_settings(**overrides):
    base = {
        "TWILIO_ACCOUNT_SID": "ACtest",
        "TWILIO_AUTH_TOKEN": "token",
        "TWILIO_FROM_NUMBER": "+15125550000",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


# --------------------------- normalize_phone ---------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("(512) 555-1212", "+15125551212"),
        ("512.555.1212", "+15125551212"),
        ("512 555 1212", "+15125551212"),
        ("5125551212", "+15125551212"),
        ("15125551212", "+15125551212"),
        ("+15125551212", "+15125551212"),
        ("+44 20 7946 0958", "+442079460958"),
        (None, None),
        ("", None),
        ("   ", None),
        ("ext. 42", None),  # too short to be a number
        ("123", None),
        ("512-555-121", None),  # 9 digits, no + prefix
    ],
)
def test_normalize_phone(raw: str | None, expected: str | None) -> None:
    assert normalize_phone(raw) == expected


# --------------------------- send_sms ---------------------------


@respx.mock
async def test_send_sms_posts_to_twilio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sms_mod, "get_settings", lambda: _fake_settings())
    route = respx.post(TWILIO).mock(return_value=httpx.Response(201, json={"sid": "SM1"}))

    ok = await send_sms(
        to="+15125551212",
        body="New work order",
        media_urls=["https://blob/a?sig=1", "https://blob/b?sig=2"],
    )

    assert ok is True
    assert route.called
    sent = route.calls.last.request
    content = sent.content.decode()
    assert "To=%2B15125551212" in content
    assert "From=%2B15125550000" in content
    assert content.count("MediaUrl=") == 2
    # HTTP basic auth with the account SID + token.
    assert sent.headers["authorization"].startswith("Basic ")


async def test_send_sms_skips_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sms_mod, "get_settings", lambda: _fake_settings(TWILIO_ACCOUNT_SID=""))
    # No respx mock registered — a real POST attempt would error the test.
    assert await send_sms(to="+15125551212", body="x") is False


async def test_send_sms_skips_without_from_number(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sms_mod, "get_settings", lambda: _fake_settings(TWILIO_FROM_NUMBER=""))
    assert await send_sms(to="+15125551212", body="x") is False


@respx.mock
async def test_send_sms_returns_false_on_twilio_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sms_mod, "get_settings", lambda: _fake_settings())
    respx.post(TWILIO).mock(return_value=httpx.Response(400, json={"message": "unverified number"}))
    assert await send_sms(to="+15125551212", body="x") is False


@respx.mock
async def test_send_sms_caps_media_count(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sms_mod, "get_settings", lambda: _fake_settings())
    route = respx.post(TWILIO).mock(return_value=httpx.Response(201, json={"sid": "SM1"}))

    await send_sms(
        to="+15125551212",
        body="x",
        media_urls=[f"https://blob/{i}" for i in range(15)],
    )

    content = route.calls.last.request.content.decode()
    assert content.count("MediaUrl=") == sms_mod.MAX_MMS_MEDIA
