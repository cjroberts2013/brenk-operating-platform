"""Compose and classify inbound vendor SMS replies (pure, no DB / no I/O).

When a vendor texts our toll-free number back, the webhook logs it and
forwards a readable version to Daryl (Charles first). Two shapes:

- A normal reply ("can be there at 2pm") -> forward with vendor + WO
  context so Daryl knows who said what about which job.
- An opt-out ("STOP") -> a distinct ALERT, because Twilio has now blocked
  that vendor from receiving texts and Daryl must reach them another way
  for future dispatches.

This module is the single source of truth for the reply message shapes and
the opt-out keyword set; the endpoint handles the DB write + the send.
"""

from __future__ import annotations

# Twilio's standard opt-out keywords (carrier-level STOP set). A reply that
# IS one of these (case-insensitive, trimmed) means the vendor opted out.
_OPT_OUT_KEYWORDS = frozenset(
    {"stop", "stopall", "unsubscribe", "cancel", "end", "quit", "revoke", "optout"}
)


def is_opt_out(body: str | None) -> bool:
    """True if the reply body is exactly a Twilio opt-out keyword."""
    if not body:
        return False
    return body.strip().lower() in _OPT_OUT_KEYWORDS


def _vendor_label(vendor_name: str | None, from_number: str) -> str:
    return vendor_name or f"an unrecognized number ({from_number})"


def compose_reply_forward(
    *,
    vendor_name: str | None,
    from_number: str,
    body: str,
    wo_number: str | None,
    location: str | None,
) -> str:
    """Forward text for a normal (non-opt-out) vendor reply."""
    who = _vendor_label(vendor_name, from_number)
    context = ""
    if wo_number:
        loc = f", {location}" if location else ""
        context = f" (likely WO {wo_number}{loc})"
    return f'{who} replied{context}:\n"{body.strip()}"'


def compose_opt_out_alert(
    *,
    vendor_name: str | None,
    from_number: str,
) -> str:
    """Alert text when a vendor opts out — Daryl must reach them elsewhere."""
    who = _vendor_label(vendor_name, from_number)
    return (
        f"⚠️ {who} replied STOP and has opted OUT of text messages. "
        "They will no longer receive dispatch texts — reach them another way "
        "(call/email) for future work orders."
    )
