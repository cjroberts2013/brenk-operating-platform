"""Unit tests for the invoice submit builder (pure, no DB / no SC)."""

from decimal import Decimal

from app.models.work_order import WorkOrder
from app.services.invoice_submit import (
    build_payload,
    compute_preview,
    make_invoice_number,
    marked_up_amount,
)


def _wo(**overrides) -> WorkOrder:
    defaults = dict(
        sc_work_order_id=999000001,
        sc_number="351182931",
        primary_status="COMPLETED",
        extended_status="CONFIRMED",
        brenk_labor_cost=Decimal("100.00"),
        brenk_material_cost=Decimal("50.00"),
        brenk_markup_percent=Decimal("65.00"),
        nte=Decimal("300.00"),
        resolution="Replaced the gate loop detector.",
    )
    defaults.update(overrides)
    return WorkOrder(**defaults)


# --------------------------------------------------------------------------- #
# Amount math
# --------------------------------------------------------------------------- #
def test_marked_up_amount_rounds_half_up() -> None:
    # 1154.99 * 1.65 = 1905.7335 -> 1905.73
    assert marked_up_amount(Decimal("1154.99"), Decimal("65")) == Decimal("1905.73")
    assert marked_up_amount(None, Decimal("65")) == Decimal("0.00")


def test_preview_totals_are_sum_of_rounded_components() -> None:
    wo = _wo(
        brenk_labor_cost=Decimal("33.33"),
        brenk_material_cost=Decimal("66.67"),
        brenk_markup_percent=Decimal("10.00"),
        nte=Decimal("999.00"),
    )
    p = compute_preview(wo, 0)
    assert p.labor_amount == Decimal("36.66")  # 36.663 -> 36.66
    assert p.material_amount == Decimal("73.34")  # 73.337 -> 73.34
    assert p.subtotal == Decimal("110.00")
    assert p.tax_amount == Decimal("9.08")  # 110.00 * 0.0825 = 9.075 -> 9.08
    assert p.invoice_total == Decimal("119.08")  # subtotal + tax


# --------------------------------------------------------------------------- #
# Invoice number
# --------------------------------------------------------------------------- #
def test_invoice_number_alphanumeric_and_suffixed() -> None:
    assert make_invoice_number("351182931  ", 0) == "BRENK351182931"
    assert make_invoice_number("351-182.931", 0) == "BRENK351182931"  # ^\w*$ rule
    assert make_invoice_number("351182931", 1) == "BRENK351182931R2"
    assert make_invoice_number("351182931", 2) == "BRENK351182931R3"


# --------------------------------------------------------------------------- #
# Validation problems
# --------------------------------------------------------------------------- #
def test_eligible_wo_has_no_problems() -> None:
    p = compute_preview(_wo(), 0)
    assert p.eligible, p.problems
    assert p.subtotal == Decimal("247.50")  # 165 + 82.50
    assert p.tax_amount == Decimal("20.42")  # 247.50 * 0.0825 = 20.41875
    assert p.invoice_total == Decimal("267.92")  # under NTE 300


def test_not_ready_stage_blocks() -> None:
    p = compute_preview(_wo(primary_status="IN PROGRESS", extended_status=None), 0)
    assert any("isn't ready to invoice" in s for s in p.problems)


def test_missing_markup_and_costs_block() -> None:
    p = compute_preview(
        _wo(brenk_markup_percent=None, brenk_labor_cost=None, brenk_material_cost=None), 0
    )
    # With no markup and no total, a single "price it first" message.
    assert any("No markup or total" in s for s in p.problems)


def test_markup_set_but_no_costs_blocks() -> None:
    p = compute_preview(_wo(brenk_labor_cost=None, brenk_material_cost=None), 0)
    assert any("No vendor costs" in s for s in p.problems)


# --------------------------------------------------------------------------- #
# Direct-total (override) path — Daryl prices by the total, no cost breakdown
# --------------------------------------------------------------------------- #
def test_total_override_bills_as_single_labor_line() -> None:
    wo = _wo(
        brenk_markup_percent=None,
        brenk_labor_cost=None,
        brenk_material_cost=None,
        brenk_total_override=Decimal("200.00"),
    )
    p = compute_preview(wo, 0)
    assert p.eligible, p.problems
    assert p.labor_amount == Decimal("200.00")  # whole total bills as labor
    assert p.material_amount == Decimal("0.00")
    assert p.subtotal == Decimal("200.00")
    assert p.tax_amount == Decimal("16.50")  # 200 * 0.0825
    assert p.invoice_total == Decimal("216.50")

    payload = build_payload(p, wo)
    assert payload["InvoiceTotal"] == 216.50
    # Standard (flat-rate) form: the whole total rides as LaborAmount.
    assert payload["InvoiceAmountsDetails"]["LaborAmount"] == 200.00
    assert payload["InvoiceAmountsDetails"]["MaterialAmount"] == 0.0


def test_total_override_respects_nte_including_tax() -> None:
    wo = _wo(
        brenk_markup_percent=None,
        brenk_labor_cost=None,
        brenk_material_cost=None,
        brenk_total_override=Decimal("280.00"),  # +8.25% = 303.10 > NTE 300
    )
    p = compute_preview(wo, 0)
    assert any("exceeds NTE" in s for s in p.problems)


def test_total_override_must_be_positive() -> None:
    wo = _wo(
        brenk_markup_percent=None,
        brenk_labor_cost=None,
        brenk_material_cost=None,
        brenk_total_override=Decimal("0.00"),
    )
    p = compute_preview(wo, 0)
    assert any("greater than zero" in s for s in p.problems)


def test_over_nte_blocks() -> None:
    p = compute_preview(_wo(nte=Decimal("200.00")), 0)  # total 267.92 > 200
    assert any("exceeds NTE" in s for s in p.problems)


def test_tax_pushing_total_over_nte_blocks() -> None:
    # Subtotal 247.50 fits under NTE 250, but +8.25% tax (267.92) doesn't —
    # the NTE check must include tax, like SC's own validation will.
    p = compute_preview(_wo(nte=Decimal("250.00")), 0)
    assert any("exceeds NTE" in s for s in p.problems)


def test_active_sc_invoice_blocks_but_void_does_not() -> None:
    blocked = compute_preview(_wo(sc_invoice_status="Open", sc_invoice_number="BRENK1"), 0)
    assert any("already exists" in s for s in blocked.problems)
    ok = compute_preview(_wo(sc_invoice_status="Void", sc_invoice_number="BRENK1"), 1)
    assert ok.eligible, ok.problems
    assert ok.invoice_number.endswith("R2")  # re-invoice gets a fresh number


def test_missing_resolution_blocks_until_text_supplied() -> None:
    wo = _wo(resolution=None)
    assert any("Resolution text" in s for s in compute_preview(wo, 0).problems)
    p = compute_preview(wo, 0, invoice_text="Did the thing.")
    assert p.eligible, p.problems
    assert p.resolution_text == "Did the thing."


# --------------------------------------------------------------------------- #
# Payload shape
# --------------------------------------------------------------------------- #
def test_payload_carries_marked_up_amounts_only() -> None:
    wo = _wo()
    p = compute_preview(wo, 0)
    payload = build_payload(p, wo)
    assert payload["InvoiceNumber"] == "BRENK351182931"
    assert payload["WoIdentifier"] == "351182931"
    assert payload["InvoiceTotal"] == 267.92  # 247.50 subtotal + 20.42 tax
    assert payload["InvoiceTax"] == 20.42  # 8.25% TX sales tax
    assert payload["InvoiceAmountsDetails"]["LaborAmount"] == 165.0
    assert payload["InvoiceAmountsDetails"]["MaterialAmount"] == 82.5
    # Standard (flat-rate) form: totals only, no itemized line arrays.
    assert "Labors" not in payload
    assert "Materials" not in payload
    # Confidentiality: raw vendor costs (100/50) and the markup % (65)
    # never appear as values, and no brenk_* field leaks.
    amounts = payload["InvoiceAmountsDetails"]
    assert 100.0 not in amounts.values()
    assert 50.0 not in amounts.values()
    assert 65.0 not in amounts.values()
    assert "brenk_" not in str(payload).lower()
    assert "markup" not in str(payload).lower()


def test_payload_is_standard_form_never_itemized() -> None:
    # No line-item arrays are ever sent — Standard (flat-rate) form only.
    wo = _wo(brenk_material_cost=None)
    p = compute_preview(wo, 0)
    payload = build_payload(p, wo)
    assert "Labors" not in payload
    assert "Materials" not in payload
    assert payload["InvoiceAmountsDetails"]["MaterialAmount"] == 0.0
