"""Unit tests for inbound vendor-reply classification + composition."""

import pytest

from app.services.sms_inbound import (
    compose_opt_out_alert,
    compose_reply_forward,
    is_opt_out,
)


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("STOP", True),
        ("stop", True),
        ("  Stop  ", True),
        ("UNSUBSCRIBE", True),
        ("cancel", True),
        ("QUIT", True),
        ("can be there at 2pm", False),
        ("stopping by tomorrow", False),  # substring must not match
        ("", False),
        (None, False),
    ],
)
def test_is_opt_out(body, expected) -> None:
    assert is_opt_out(body) is expected


def test_reply_forward_with_full_context() -> None:
    text = compose_reply_forward(
        vendor_name="Larry's Locksmith",
        from_number="+15125551212",
        body="Can be there at 2pm",
        wo_number="356043995",
        location="4471 CubeSmart Converse",
    )
    assert text == (
        "Larry's Locksmith replied (likely WO 356043995, 4471 CubeSmart Converse):\n"
        '"Can be there at 2pm"'
    )


def test_reply_forward_without_wo_context() -> None:
    text = compose_reply_forward(
        vendor_name="Larry's Locksmith",
        from_number="+15125551212",
        body="On my way",
        wo_number=None,
        location=None,
    )
    assert text == 'Larry\'s Locksmith replied:\n"On my way"'


def test_reply_forward_unknown_number() -> None:
    text = compose_reply_forward(
        vendor_name=None,
        from_number="+15125550000",
        body="who is this?",
        wo_number=None,
        location=None,
    )
    assert "an unrecognized number (+15125550000)" in text
    assert '"who is this?"' in text


def test_opt_out_alert_named_vendor() -> None:
    text = compose_opt_out_alert(vendor_name="Larry's Locksmith", from_number="+15125551212")
    assert "Larry's Locksmith" in text
    assert "opted OUT" in text
    assert "reach them another way" in text.lower() or "another way" in text


def test_opt_out_alert_unknown_number() -> None:
    text = compose_opt_out_alert(vendor_name=None, from_number="+15125550000")
    assert "+15125550000" in text
    assert "opted OUT" in text
