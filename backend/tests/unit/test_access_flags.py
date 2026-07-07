"""Unit tests for customer-unit access detection (pure, no DB).

Positive cases are real phrases from prod descriptions/notes
(2026-07-07 calibration scan); negative cases are the false-positive
traps found in the same scan.
"""

import pytest

from app.models.work_order import WorkOrder, WorkOrderNote
from app.services.access_flags import (
    apply_description_flag,
    apply_note_flag,
    is_flag_active,
    scan_for_access_signal,
)

# --------------------------------------------------------------------------- #
# scan_for_access_signal
# --------------------------------------------------------------------------- #

REAL_POSITIVES = [
    # description phrasing
    "A client rents the unit out, but I have there key to gain access.",
    "nor did she feel comfortable leaving a key with us",
    "unless they sign a key release form and leave a key with the office",
    "We have a key for their cube. They are needing in their cube",
    "J319 key on file. / POSSIBLE RECALL FROM TN #341426823",
    "so they can meet them here with the key",
    "Occupied exterior drive up cube 4034 has water intrusion",
    "During property noticed customer unit door open with the hasp cut",
    # note phrasing
    "Cus did not leave a key. For them to set a time or bring a key.",
    "Unit is occupied, tenant is on vacation, so wasnt able to gain access. "
    "Tenant will drop key off when he's back",
    "So i can reach the customer and have them meet us at the unit.",
    "This will have to be set up with the tenant",
    "The tenant in Wine Storage Unit W1102 is asking if we can add the floor",
]

REAL_NEGATIVES = [
    # false-positive traps from the same scan
    "I believe there is a proposal in , I think their waiting for approval",
    "I am waiting for the proposal to be approved.",
    "This work order has been rescheduled to Saturday 25th due to weather conditions.",
    "installed a door handle to prevent it from being opened without a key. "
    "Please adjust NTE to $ 324.75.",
    "The 3 backflow inspection is scheduled for this Friday 5/15",
    "Our alarm panel is still waiting for the replacement battery.",
    "Scheduled Date has been changed from May 6 to May 7.",
    # Prod backfill dry-run FP (2026-07-07): "Tenant" as a place name.
    "Day of the week access will be granted?: M-F / Building #: Tenant "
    "Parking Area / The parking area gate is damaged",
    "",
]


@pytest.mark.parametrize("text", REAL_POSITIVES)
def test_scan_matches_real_positives(text: str) -> None:
    signal = scan_for_access_signal(text)
    assert signal is not None, f"expected a match: {text!r}"
    assert signal.snippet  # snippet always populated on a match


@pytest.mark.parametrize("text", REAL_NEGATIVES)
def test_scan_ignores_real_negatives(text: str) -> None:
    assert scan_for_access_signal(text) is None, f"false positive: {text!r}"


def test_scan_snippet_is_trimmed_with_ellipses() -> None:
    long = "x" * 300 + " tenant will drop key off tomorrow " + "y" * 300
    signal = scan_for_access_signal(long)
    assert signal is not None
    assert signal.snippet.startswith("…")
    assert signal.snippet.endswith("…")
    assert "drop key off" in signal.snippet


# --------------------------------------------------------------------------- #
# apply_* flag lifecycle
# --------------------------------------------------------------------------- #


def _wo(**overrides) -> WorkOrder:
    defaults = dict(
        sc_work_order_id=999,
        sc_number="999",
        primary_status="OPEN",
        description="Customer did not leave a key with the office.",
    )
    defaults.update(overrides)
    return WorkOrder(**defaults)


def _note(text: str, note_type: str = "UsersNote", note_id: int = 1) -> WorkOrderNote:
    n = WorkOrderNote(note_data=text, note_type=note_type)
    n.id = note_id
    return n


def test_description_flag_sets_fields() -> None:
    wo = _wo()
    assert apply_description_flag(wo) is True
    assert is_flag_active(wo)
    assert wo.brenk_access_flag_source == "description"
    assert "leave a key" in wo.brenk_access_flag_snippet
    # Second scan is a no-op — first receipt wins.
    assert apply_description_flag(wo) is False


def test_description_flag_no_signal() -> None:
    wo = _wo(description="Replace the ballast in hallway light fixture.")
    assert apply_description_flag(wo) is False
    assert wo.brenk_access_flag_at is None


def test_dismissed_description_flag_stays_dismissed() -> None:
    wo = _wo()
    apply_description_flag(wo)
    wo.brenk_access_flag_dismissed_at = wo.brenk_access_flag_at
    # Re-running the description scan (e.g. hourly sync) must NOT re-open.
    assert apply_description_flag(wo) is False
    assert not is_flag_active(wo)


def test_note_flag_sets_and_system_notes_ignored() -> None:
    wo = _wo(description="No signal here.")
    system = _note("tenant must leave a key", note_type="SystemNote")
    assert apply_note_flag(wo, system) is False

    human = _note("Tenant will drop key off when he's back in town", note_id=7)
    assert apply_note_flag(wo, human) is True
    assert wo.brenk_access_flag_source == "note"
    assert wo.brenk_access_flag_note_id == 7


def test_new_note_reopens_dismissed_flag() -> None:
    wo = _wo()
    apply_description_flag(wo)
    wo.brenk_access_flag_dismissed_at = wo.brenk_access_flag_at  # operator dismissed

    note = _note("Store says customer has to bring a key before work can start", note_id=9)
    assert apply_note_flag(wo, note) is True
    assert is_flag_active(wo)  # fresh evidence re-opened it
    assert wo.brenk_access_flag_note_id == 9


def test_active_flag_not_overwritten_by_later_note() -> None:
    wo = _wo()
    apply_description_flag(wo)
    first_snippet = wo.brenk_access_flag_snippet
    note = _note("another tenant key note", note_id=11)
    assert apply_note_flag(wo, note) is False
    assert wo.brenk_access_flag_snippet == first_snippet
