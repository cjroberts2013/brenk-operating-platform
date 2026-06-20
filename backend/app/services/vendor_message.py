"""Compose the ready-to-send vendor notification message for a work order.

When Daryl assigns a sub-vendor, this builds the plain-text message he
texts/emails them: WO number, store + address, known gate code(s), the
work description, and the attached photos. One body that pastes cleanly
into SMS or email, plus a suggested email subject.

This is the single source of truth for the message shape — Phase 3
auto-send (Twilio/Resend) will compose from here too.

Deliberately EXCLUDED from the vendor-facing body:
- NTE — the client-side ceiling; never anchor the vendor's price to it.
- The vendor's `communication_notes` — Brenk-internal operator hints.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Any

from app.models.work_order import GateCode, Vendor, WorkOrder
from app.services.addresses import format_address

_SIGNOFF = "Please confirm you can take this and your ETA. Thanks!\n— Brenk Facility Services"

# Cap total photo bytes attached to one email. Resend allows ~40 MB; stay
# well under so a big photo set degrades to "no attachments" rather than a
# rejected send. Photos run ~3 MB each, so this is several photos.
MAX_TOTAL_ATTACHMENT_BYTES = 20 * 1024 * 1024


def text_to_html(body: str) -> str:
    """Turn the plain-text message into minimal, safe HTML (escaped, with
    line breaks preserved) for the email's HTML part."""
    return "<br>".join(html.escape(line) for line in body.split("\n"))


@dataclass
class ComposedMessage:
    subject: str
    body: str


def _gate_code_lines(active_gate_codes: list[GateCode]) -> list[str]:
    lines: list[str] = []
    for gc in active_gate_codes:
        label = f" ({gc.label})" if gc.label else ""
        lines.append(f"Gate code: {gc.code}{label}")
    return lines


def problem_summary(description: str | None) -> str:
    """Pull the actual problem out of an SC work-order description.

    SC descriptions are a breadcrumb of category + access boilerplate joined
    by " / " — e.g. "OFFICE INTERIOR / DOORS / ... / Building #: Office /
    Side door to office leaks during rain." The real problem is the final
    segment, which is all the vendor needs. Splits on " / " (spaces around
    the slash) so an in-text fraction like "1/2 inch" survives.

    Edge cases (descriptions that don't follow this shape) are handled as
    they surface; for now we take the last segment, falling back to the
    whole text, then to a placeholder.
    """
    text = (description or "").strip()
    if not text:
        return "(none provided)"
    last = text.rsplit(" / ", 1)[-1].strip()
    return last or text


def _photos_line(attachments: list[dict[str, Any]]) -> str:
    if not attachments:
        return "Photos: none"
    names = [a.get("Name") for a in attachments if a.get("Name")]
    count = len(attachments)
    noun = "photo" if count == 1 else "photos"
    if names:
        return f"Photos: {count} {noun} attached — {', '.join(names)}"
    return f"Photos: {count} {noun} attached"


def compose_vendor_message(
    *,
    wo: WorkOrder,
    store_id: str | None,
    location_name: str | None,
    location_raw_data: dict[str, Any] | None,
    trade_name: str | None,
    active_gate_codes: list[GateCode],
    attachments: list[dict[str, Any]],
    vendor: Vendor | None,
) -> ComposedMessage:
    """Build the (subject, body) for the vendor notification message."""
    location_bits = " — ".join(p for p in [store_id, location_name] if p) or "(location TBD)"
    address = format_address(location_raw_data)
    description = problem_summary(wo.description)

    lines: list[str] = ["New work order from Brenk Facility Services", ""]
    if vendor is not None and vendor.name:
        lines = [f"Hi {vendor.name}, new work order from Brenk Facility Services:", ""]

    lines.append(f"WO #: {wo.sc_number}")
    lines.append(f"Location: {location_bits}")
    if address:
        lines.append(f"Address: {address}")
    lines.extend(_gate_code_lines(active_gate_codes))
    if trade_name:
        lines.append(f"Trade: {trade_name}")
    lines.append(f"Problem: {description}")
    lines.append(_photos_line(attachments))
    lines.append("")
    lines.append(_SIGNOFF)

    subject_loc = " ".join(p for p in [store_id, location_name] if p)
    subject = f"Brenk WO {wo.sc_number}"
    if subject_loc:
        subject += f" — {subject_loc}"
    if trade_name:
        subject += f" ({trade_name})"

    return ComposedMessage(subject=subject, body="\n".join(lines))
