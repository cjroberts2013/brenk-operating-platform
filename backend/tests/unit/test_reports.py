"""Unit tests for the reports aggregation math.

DB-free: builds transient WorkOrder/Trade/Vendor instances and feeds
them straight to `build_reports_summary`.
"""

from decimal import Decimal

from app.models.work_order import Trade, Vendor, WorkOrder
from app.services.reports import build_reports_summary


def _wo(
    *,
    labor=None,
    material=None,
    markup=None,
    trade=None,
    vendor=None,
) -> WorkOrder:
    """A transient WO carrying only the fields the reports math reads."""
    wo = WorkOrder(
        sc_work_order_id=1,
        sc_number="WO-1",
        primary_status="INVOICED",
    )
    wo.brenk_labor_cost = Decimal(labor) if labor is not None else None
    wo.brenk_material_cost = Decimal(material) if material is not None else None
    wo.brenk_markup_percent = Decimal(markup) if markup is not None else None
    wo.trade = trade
    wo.assigned_vendor = vendor
    return wo


def test_empty_when_no_markup_data() -> None:
    summary = build_reports_summary([])
    assert summary.totals.jobs_with_markup == 0
    assert summary.totals.total_vendor_cost == "0.00"
    assert summary.totals.blended_markup_percent is None
    assert summary.markup_by_trade == []
    assert summary.vendor_spend == []


def test_wo_without_markup_is_ignored() -> None:
    # Costs entered but no markup % -> not yet a billable decision.
    summary = build_reports_summary([_wo(labor=100, material=50)])
    assert summary.totals.jobs_with_markup == 0


def _wo_cat(category, *, labor, markup) -> WorkOrder:
    wo = _wo(labor=labor, markup=markup)
    wo.brenk_category = category
    return wo


def test_by_category_groups_and_averages() -> None:
    summary = build_reports_summary(
        [
            _wo_cat("Plumbing", labor=100, markup=80),
            _wo_cat("Plumbing", labor=100, markup=60),
            _wo_cat("Electrical", labor=200, markup=70),
            _wo(labor=50, markup=90),  # no category → excluded from by_category
        ]
    )
    cats = {c.category: c for c in summary.markup_by_category}
    assert set(cats) == {"Plumbing", "Electrical"}
    assert cats["Plumbing"].jobs_with_markup == 2
    assert cats["Plumbing"].avg_actual_markup_percent == 70.0  # (80 + 60) / 2
    assert cats["Plumbing"].total_margin == "140.00"  # 100*.8 + 100*.6
    assert cats["Electrical"].jobs_with_markup == 1
    # Sorted alphabetically by category.
    assert [c.category for c in summary.markup_by_category] == ["Electrical", "Plumbing"]


def test_wo_with_markup_but_zero_cost_is_ignored() -> None:
    summary = build_reports_summary([_wo(markup=80)])
    assert summary.totals.jobs_with_markup == 0


def test_single_job_totals_and_margin() -> None:
    # subtotal 180, 38% markup -> margin 68.40, billed 248.40
    summary = build_reports_summary([_wo(labor=120, material=60, markup=38)])
    t = summary.totals
    assert t.jobs_with_markup == 1
    assert t.total_vendor_cost == "180.00"
    assert t.total_margin == "68.40"
    assert t.total_billed == "248.40"
    assert t.blended_markup_percent == 38.0


def test_markup_by_trade_actual_vs_default() -> None:
    doors = Trade(name="Commercial Door Repair")
    doors.id = 7
    doors.default_markup_percent = Decimal(85)
    # Two door jobs marked up at 80 and 90 -> avg 85, delta 0 vs default 85.
    summary = build_reports_summary(
        [
            _wo(labor=100, markup=80, trade=doors),
            _wo(labor=100, markup=90, trade=doors),
        ]
    )
    assert len(summary.markup_by_trade) == 1
    row = summary.markup_by_trade[0]
    assert row.trade_name == "Commercial Door Repair"
    assert row.jobs_with_markup == 2
    assert row.default_markup_percent == 85.0
    assert row.avg_actual_markup_percent == 85.0
    assert row.delta_percent == 0.0


def test_delta_none_when_trade_has_no_default() -> None:
    plumbing = Trade(name="Plumber")
    plumbing.id = 3
    plumbing.default_markup_percent = None
    summary = build_reports_summary([_wo(labor=200, markup=70, trade=plumbing)])
    row = summary.markup_by_trade[0]
    assert row.default_markup_percent is None
    assert row.avg_actual_markup_percent == 70.0
    assert row.delta_percent is None


def test_vendor_spend_sorted_by_cost_desc() -> None:
    larry = Vendor(name="Larry Marshall")
    larry.id = 76
    javier = Vendor(name="Javier Aboytes")
    javier.id = 80
    summary = build_reports_summary(
        [
            _wo(labor=100, markup=50, vendor=larry),
            _wo(labor=500, markup=50, vendor=javier),
        ]
    )
    assert [v.vendor_name for v in summary.vendor_spend] == [
        "Javier Aboytes",
        "Larry Marshall",
    ]
    assert summary.vendor_spend[0].total_vendor_cost == "500.00"


def test_markup_by_trade_sorted_case_insensitive() -> None:
    apt = Trade(name="APARTMENT TURNS")
    apt.id = 1
    appliance = Trade(name="Appliance Repair")
    appliance.id = 2
    summary = build_reports_summary(
        [
            _wo(labor=100, markup=50, trade=apt),
            _wo(labor=100, markup=50, trade=appliance),
        ]
    )
    # "Appliance" before "APARTMENT" by lowercase comparison
    assert [m.trade_name for m in summary.markup_by_trade] == [
        "APARTMENT TURNS",
        "Appliance Repair",
    ]
