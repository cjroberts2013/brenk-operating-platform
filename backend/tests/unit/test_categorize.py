"""Unit tests for the Gemini categorization client (HTTP mocked)."""

import json
from types import SimpleNamespace

import httpx
import respx

from app.services import categorize as cat


def _settings(key: str = "test-key", model: str = "gemini-flash-lite-latest") -> SimpleNamespace:
    return SimpleNamespace(GEMINI_API_KEY=key, GEMINI_MODEL=model)


def _gemini_ok(category: str, confidence: float = 0.9) -> dict:
    """Shape of a generateContent structured-output response."""
    text = json.dumps({"category": category, "confidence": confidence})
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


_GEMINI_URL = r".*generativelanguage\.googleapis\.com.*"

# The taxonomy is now passed in (loaded from the DB in production); tests
# supply a small fixed list.
_DEFS = [
    ("Electrical", "Wiring, outlets, lighting."),
    ("Plumbing", "Leaks, drains, pipes, fixtures."),
    ("Doors", "Doors and hardware."),
]


@respx.mock
async def test_categorize_parses_result(monkeypatch) -> None:
    monkeypatch.setattr(cat, "get_settings", lambda: _settings())
    route = respx.post(url__regex=_GEMINI_URL).mock(
        return_value=httpx.Response(200, json=_gemini_ok("Plumbing", 0.92))
    )
    result = await cat.categorize(
        "DOORS / OTHER ISSUES / Leaky faucet in the restroom", job_type_defs=_DEFS
    )
    assert result == ("Plumbing", 0.92)
    assert route.called
    # Only the problem line is sent, not the breadcrumb boilerplate.
    sent = json.loads(route.calls.last.request.content)
    prompt = sent["contents"][0]["parts"][0]["text"]
    assert "Leaky faucet in the restroom" in prompt
    assert "OTHER ISSUES" not in prompt


@respx.mock
async def test_categorize_rejects_out_of_taxonomy(monkeypatch) -> None:
    monkeypatch.setattr(cat, "get_settings", lambda: _settings())
    respx.post(url__regex=_GEMINI_URL).mock(
        return_value=httpx.Response(200, json=_gemini_ok("Underwater Basket Weaving"))
    )
    assert await cat.categorize("a / b / something", job_type_defs=_DEFS) is None


@respx.mock
async def test_categorize_clamps_confidence(monkeypatch) -> None:
    monkeypatch.setattr(cat, "get_settings", lambda: _settings())
    respx.post(url__regex=_GEMINI_URL).mock(
        return_value=httpx.Response(200, json=_gemini_ok("Electrical", 1.7))
    )
    result = await cat.categorize("x / y / breaker keeps tripping", job_type_defs=_DEFS)
    assert result is not None and result[0] == "Electrical" and result[1] == 1.0


@respx.mock
async def test_categorize_http_error_returns_none(monkeypatch) -> None:
    monkeypatch.setattr(cat, "get_settings", lambda: _settings())
    respx.post(url__regex=_GEMINI_URL).mock(return_value=httpx.Response(500, text="boom"))
    assert await cat.categorize("x / y / something", job_type_defs=_DEFS) is None


async def test_categorize_no_key_is_noop(monkeypatch) -> None:
    monkeypatch.setattr(cat, "get_settings", lambda: _settings(key=""))
    # No respx route registered — must not make a call.
    assert await cat.categorize("x / y / leak", job_type_defs=_DEFS) is None


async def test_categorize_no_text_is_noop(monkeypatch) -> None:
    monkeypatch.setattr(cat, "get_settings", lambda: _settings())
    assert await cat.categorize(None, job_type_defs=_DEFS) is None
    assert await cat.categorize("   ", job_type_defs=_DEFS) is None
