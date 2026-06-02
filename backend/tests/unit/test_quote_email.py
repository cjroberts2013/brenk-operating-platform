"""Tests for the storefront quote endpoint + Resend email service."""

from types import SimpleNamespace

import httpx
import pytest
import respx
from httpx import ASGITransport

import app.services.email as email_mod
from app.main import app
from app.services.email import send_email

QUOTE_URL = "/api/v1/storefront/quote"
RESEND = "https://api.resend.com/emails"


def _fake_settings(**overrides):
    base = {
        "RESEND_API_KEY": "re_test_key",
        "QUOTE_FROM_EMAIL": "Brenk <from@brenkfacilityservices.com>",
        "QUOTE_TO_EMAIL": "daryl@brenkfacilityservices.com",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


# --------------------------- email service ---------------------------


@respx.mock
async def test_send_email_posts_to_resend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(email_mod, "get_settings", lambda: _fake_settings())
    route = respx.post(RESEND).mock(return_value=httpx.Response(200, json={"id": "x"}))

    ok = await send_email(subject="s", html="<p>hi</p>", reply_to="lead@example.com")

    assert ok is True
    assert route.called
    sent = route.calls.last.request
    assert sent.headers["authorization"] == "Bearer re_test_key"


async def test_send_email_skips_when_no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(email_mod, "get_settings", lambda: _fake_settings(RESEND_API_KEY=""))
    # No respx mock registered — if it tried to POST, the call would error.
    assert await send_email(subject="s", html="<p>x</p>") is False


@respx.mock
async def test_send_email_returns_false_on_resend_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(email_mod, "get_settings", lambda: _fake_settings())
    respx.post(RESEND).mock(return_value=httpx.Response(422, json={"message": "bad"}))
    assert await send_email(subject="s", html="<p>x</p>") is False


# --------------------------- endpoint ---------------------------


async def _post(json: dict) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.post(QUOTE_URL, json=json)


@respx.mock
async def test_quote_endpoint_sends(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(email_mod, "get_settings", lambda: _fake_settings())
    route = respx.post(RESEND).mock(return_value=httpx.Response(200, json={"id": "x"}))

    r = await _post(
        {"name": "Jane", "email": "jane@example.com", "phone": "5551234", "message": "Need a bid"}
    )

    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "emailed": True}
    assert route.called


async def test_quote_endpoint_honeypot_silently_dropped() -> None:
    # Honeypot filled -> accepted but not emailed, and no Resend call made
    # (no respx mock here; a send attempt would raise a connection error).
    r = await _post(
        {
            "name": "Bot",
            "email": "bot@example.com",
            "message": "spam",
            "website": "http://spam.example",
        }
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True, "emailed": False}


async def test_quote_endpoint_rejects_bad_email() -> None:
    r = await _post({"name": "Jane", "email": "not-an-email", "message": "hi"})
    assert r.status_code == 422


async def test_quote_endpoint_requires_message() -> None:
    r = await _post({"name": "Jane", "email": "jane@example.com", "message": ""})
    assert r.status_code == 422
