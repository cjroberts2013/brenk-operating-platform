"""Customer-unit access detection ("call ahead before you show up").

Work inside a tenant's storage unit needs the tenant present with a key
(or a key left at the office). The signal shows up in the WO description
at creation, or days later in a store manager's note. Missing it means a
vendor drives out and can't work — this module is the single source of
truth for spotting that signal.

Detection is a curated regex list, calibrated against real prod
descriptions and notes (2026-07-07 scan; see CLAUDE.md). Deliberately
keyword-based for v1: transparent, free, instant, and a false positive
costs one click to dismiss while a false negative costs a wasted trip.
Scan ONLY human text — WO descriptions and `UsersNote` notes. SystemNote
rows are automated status noise ("WAITING FOR APPROVAL", reschedules)
that false-positives heavily.

Real phrases these patterns were built from:
  "she didn't feel comfortable leaving a key with us"
  "Cus did not leave a key ... set a time or bring a key"
  "tenant will drop key off when he's back"
  "unless they sign a key release form and leave a key with the office"
  "have them meet us at the unit" / "meet them here with the key"
  "Unit is occupied, tenant is on vacation, so wasnt able to gain access"
  "We have a key for their cube" / "J319 key on file"
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from app.models.work_order import WorkOrder, WorkOrderNote

logger = structlog.get_logger(__name__)

# The only note_type whose text is human-written; SystemNote is automated.
HUMAN_NOTE_TYPE = "UsersNote"

# How much context to keep around a match for display in the UI and the
# vendor message. Whole notes can be long; the snippet is the receipt.
_SNIPPET_RADIUS = 80

# (label, pattern) — label is a short human explanation of what matched.
# Order matters only for which label wins when several match; put the
# most specific/telling patterns first.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "key coordination",
        re.compile(
            r"unit key|key release|key (?:on|in) file|key to gain access"
            r"|(?:leave|leaves|leaving|left|bring|brings|bringing|brought"
            r"|drop(?:ping|ped)?(?: off)?) (?:a |the |his |her |their )?key"
            r"|key (?:with (?:us|the office))"
            r"|(?:wait(?:ing)? (?:for|on)) (?:a |the )?key"
            r"|key (?:for|to) (?:their|his|her|the (?:customer|tenant))",
            re.IGNORECASE,
        ),
    ),
    (
        "meet on site",
        re.compile(
            r"meet (?:us|them|you|the (?:tech|vendor))|call (?:ahead|before|first)"
            r"|by appointment|(?:set|setting) (?:this |it |that )?up with the (?:tenant|customer)"
            r"|schedule[d]? with the (?:tenant|customer)",
            re.IGNORECASE,
        ),
    ),
    (
        "occupied unit",
        re.compile(
            r"\boccupied\b|customer'?s? (?:unit|cube)|tenant'?s? (?:unit|cube)"
            r"|their cube|\btenants?\b",
            re.IGNORECASE,
        ),
    ),
]


@dataclass
class AccessSignal:
    """A detected customer-unit access signal."""

    label: str
    snippet: str


def scan_for_access_signal(text: str | None) -> AccessSignal | None:
    """Scan human-written text for a customer-unit access signal.

    Returns the first (most specific) match with a display snippet, or
    None. Pass WO descriptions and UsersNote bodies only — never
    SystemNote content.
    """
    if not text:
        return None
    for label, pattern in _PATTERNS:
        m = pattern.search(text)
        if m is not None:
            start = max(0, m.start() - _SNIPPET_RADIUS)
            end = min(len(text), m.end() + _SNIPPET_RADIUS)
            snippet = text[start:end].strip()
            if start > 0:
                snippet = f"…{snippet}"
            if end < len(text):
                snippet = f"{snippet}…"
            return AccessSignal(label=label, snippet=snippet)
    return None


def is_flag_active(wo: WorkOrder) -> bool:
    """True when the WO carries a live (not dismissed) access flag."""
    return wo.brenk_access_flag_at is not None and wo.brenk_access_flag_dismissed_at is None


def apply_description_flag(wo: WorkOrder) -> bool:
    """Scan the WO's description and set the flag. Returns True if newly set.

    Only fires when the WO has never been flagged — a dismissal sticks for
    the description (it doesn't change meaningfully after creation); only
    NEW note evidence re-opens a dismissed flag.
    """
    if wo.brenk_access_flag_at is not None:
        return False
    signal = scan_for_access_signal(wo.description)
    if signal is None:
        return False
    wo.brenk_access_flag_at = datetime.now(UTC)
    wo.brenk_access_flag_source = "description"
    wo.brenk_access_flag_note_id = None
    wo.brenk_access_flag_snippet = signal.snippet
    logger.info(
        "access_flag_set",
        sc_work_order_id=wo.sc_work_order_id,
        source="description",
        label=signal.label,
    )
    return True


def apply_note_flag(wo: WorkOrder, note: WorkOrderNote) -> bool:
    """Scan a newly-synced note and set/re-open the flag. Returns True if set.

    Only human notes count. A matching NEW note re-opens a dismissed flag —
    fresh evidence ("store manager says wait for the unit key") beats an old
    dismissal. Already-active flags are left alone (first receipt wins).
    """
    if note.note_type != HUMAN_NOTE_TYPE:
        return False
    if is_flag_active(wo):
        return False
    signal = scan_for_access_signal(note.note_data)
    if signal is None:
        return False
    wo.brenk_access_flag_at = datetime.now(UTC)
    wo.brenk_access_flag_source = "note"
    wo.brenk_access_flag_note_id = note.id
    wo.brenk_access_flag_snippet = signal.snippet
    wo.brenk_access_flag_dismissed_at = None
    logger.info(
        "access_flag_set",
        sc_work_order_id=wo.sc_work_order_id,
        source="note",
        note_id=note.id,
        label=signal.label,
    )
    return True
