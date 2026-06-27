"""Unit tests for the vendor notification message composer (pure, no DB)."""

from decimal import Decimal

from app.models.work_order import GateCode, Vendor, WorkOrder
from app.services.vendor_message import compose_vendor_message, problem_summary

_RAW = {
    "Address1": "838 North Loop 1604 East",
    "City": "San Antonio",
    "State": "TX",
    "Zip": "78232",
}


def _wo(**overrides) -> WorkOrder:
    defaults = dict(
        sc_work_order_id=343852740,
        sc_number="343852740",
        primary_status="IN PROGRESS",
        description="Front gate motor not responding.",
        nte=Decimal("750.00"),
    )
    defaults.update(overrides)
    return WorkOrder(**defaults)


def _vendor(**overrides) -> Vendor:
    defaults = dict(
        name="Larry's Locksmith",
        phone="+15125551212",
        email="larry@example.com",
        contact_preference="sms",
        communication_notes="Don't text after 6pm — SECRETHINT",
    )
    defaults.update(overrides)
    return Vendor(**defaults)


def _gate(code: str, label: str | None = None) -> GateCode:
    return GateCode(code=code, label=label, is_active=True)


def _compose(**overrides):
    kwargs = dict(
        wo=_wo(),
        store_id="0751",
        location_name="0751 CUBESMART TX AUSTIN EAST STASSNEY LANE",
        location_raw_data=_RAW,
        trade_name="GATE/KEY PADS",
        active_gate_codes=[],
        attachments=[],
        vendor=_vendor(),
    )
    kwargs.update(overrides)
    return compose_vendor_message(**kwargs)


def test_includes_core_fields() -> None:
    msg = _compose()
    assert "WO #: 343852740" in msg.body
    assert "0751" in msg.body
    assert "838 North Loop 1604 East, San Antonio, TX 78232" in msg.body
    assert "Trade: GATE/KEY PADS" in msg.body
    assert "Front gate motor not responding." in msg.body
    assert "Larry's Locksmith" in msg.body  # greeting
    # Subject shape
    assert msg.subject.startswith("Brenk WO 343852740 — 0751")
    assert "(GATE/KEY PADS)" in msg.subject


def test_gate_code_present_and_labeled() -> None:
    msg = _compose(active_gate_codes=[_gate("1234#", "front gate"), _gate("9000")])
    assert "Gate code: 1234# (front gate)" in msg.body
    assert "Gate code: 9000" in msg.body


def test_no_gate_code_omits_line() -> None:
    msg = _compose(active_gate_codes=[])
    assert "Gate code" not in msg.body


def test_photos_present_lists_names_and_count() -> None:
    msg = _compose(attachments=[{"Name": "IMG_1.jpeg"}, {"Name": "IMG_2.png"}])
    assert "Photos: 2 photos attached — IMG_1.jpeg, IMG_2.png" in msg.body


def test_photos_singular_and_none() -> None:
    assert "Photos: 1 photo attached — a.jpg" in _compose(attachments=[{"Name": "a.jpg"}]).body
    assert "Photos: none" in _compose(attachments=[]).body


def test_empty_description_falls_back() -> None:
    assert "Problem: (none provided)" in _compose(wo=_wo(description=None)).body


def test_problem_summary_takes_last_segment() -> None:
    desc = (
        "OFFICE INTERIOR / DOORS / GLASS DOOR -NON SLIDING / OTHER ISSUES / "
        "Please enter contact information for vendor for access: 512-268-4171 / "
        "Store access hours for repairs to be completed?: 9:30 to 6:00 / "
        "Day of the week access will be granted?: Monday thru Friday / "
        "Building #: Office / "
        "Side door to office leaks during rain through the top of the door."
    )
    assert (
        problem_summary(desc)
        == "Side door to office leaks during rain through the top of the door."
    )


def test_problem_summary_edge_cases() -> None:
    # No breadcrumb separator → whole text.
    assert problem_summary("Just a plain problem") == "Just a plain problem"
    # In-text fraction (no spaces around the slash) survives.
    assert problem_summary("OTHER / Leaves a 1/2 inch gap") == "Leaves a 1/2 inch gap"
    # Empty / whitespace → placeholder.
    assert problem_summary(None) == "(none provided)"
    assert problem_summary("   ") == "(none provided)"


def test_compose_uses_parsed_problem() -> None:
    desc = "DOORS / OTHER ISSUES / Building #: 1 / Glass door cracked."
    body = _compose(wo=_wo(description=desc)).body
    assert "Problem: Glass door cracked." in body
    # The boilerplate breadcrumb is gone from the message.
    assert "OTHER ISSUES" not in body
    assert "Building #" not in body


def test_nte_never_appears() -> None:
    # NTE is the client ceiling — must never anchor the vendor's price.
    msg = _compose(active_gate_codes=[_gate("1234#")], attachments=[{"Name": "x.jpg"}])
    assert "750" not in msg.body
    assert "NTE" not in msg.body.upper()


def test_communication_notes_never_appears() -> None:
    # Brenk-internal operator hint — not vendor-facing.
    msg = _compose()
    assert "SECRETHINT" not in msg.body
    assert "6pm" not in msg.body


def test_works_without_vendor() -> None:
    msg = _compose(vendor=None)
    assert "WO #: 343852740" in msg.body
    assert msg.body.startswith("New work order from Brenk Facility Services")
