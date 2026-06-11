"""Unit tests for the dashboard money-stats aggregation.

DB-free: builds transient WorkOrder instances and feeds them straight
to `compute_money_stats`, pinning `now` for deterministic month math.
"""

from datetime import UTC, datetime
from decimal import Decimal

from app.models.work_order import WorkOrder
from app.services.money import BUSINESS_TZ, compute_money_stats

# Mid-June in business time; month boundary is 2026-06-01 00:00 CDT.
NOW = datetime(2026, 6, 15, 12, 0, tzinfo=BUSINESS_TZ)


def _wo(
    *,
    primary="COMPLETED",
    extended="CONFIRMED",
    labor=None,
    material=None,
    markup=None,
    nte=None,
    sc_invoice_status=None,
    sc_invoice_total=None,
    brenk_paid_at=None,
    sc_paid_at=None,
) -> WorkOrder:
    """A transient WO carrying only the fields the money math reads."""
    wo = WorkOrder(
        sc_work_order_id=1,
        sc_number="WO-1",
        primary_status=primary,
    )
    wo.extended_status = extended
    wo.brenk_labor_cost = Decimal(labor) if labor is not None else None
    wo.brenk_material_cost = Decimal(material) if material is not None else None
    wo.brenk_markup_percent = Decimal(markup) if markup is not None else None
    wo.nte = Decimal(nte) if nte is not None else None
    wo.sc_invoice_status = sc_invoice_status
    wo.sc_invoice_total = Decimal(sc_invoice_total) if sc_invoice_total is not None else None
    wo.brenk_paid_at = brenk_paid_at
    wo.sc_paid_at = sc_paid_at
    wo.assigned_vendor_id = None
    return wo


def test_empty() -> None:
    stats = compute_money_stats([], now=NOW)
    assert stats.unbilled_priced_total == "0.00"
    assert stats.unbilled_unpriced_count == 0
    assert stats.awaiting_total == "0.00"
    assert stats.paid_month_count == 0
    assert stats.paid_month_profit is None
    assert stats.month_label == "June"


def test_unbilled_priced_uses_brenk_total_bill() -> None:
    # (100 + 50) * 1.80 = 270.00
    stats = compute_money_stats([_wo(labor=100, material=50, markup=80, nte=400)], now=NOW)
    assert stats.unbilled_priced_total == "270.00"
    assert stats.unbilled_priced_count == 1
    assert stats.unbilled_unpriced_count == 0


def test_unbilled_unpriced_falls_back_to_nte() -> None:
    stats = compute_money_stats([_wo(nte=250)], now=NOW)
    assert stats.unbilled_priced_count == 0
    assert stats.unbilled_unpriced_count == 1
    assert stats.unbilled_unpriced_nte_total == "250.00"


def test_markup_without_costs_counts_as_unpriced() -> None:
    # A markup % alone can't price the job.
    stats = compute_money_stats([_wo(markup=80, nte=250)], now=NOW)
    assert stats.unbilled_priced_count == 0
    assert stats.unbilled_unpriced_count == 1


def test_pending_confirmation_not_unbilled() -> None:
    # Still awaiting the store -> work_complete stage, not ready_to_invoice.
    stats = compute_money_stats([_wo(extended="PENDING CONFIRMATION", nte=250)], now=NOW)
    assert stats.unbilled_unpriced_count == 0


def test_canceled_excluded_everywhere() -> None:
    stats = compute_money_stats([_wo(extended="CANCELED", nte=250)], now=NOW)
    assert stats.unbilled_priced_count == 0
    assert stats.unbilled_unpriced_count == 0
    assert stats.awaiting_count == 0


def test_active_invoice_moves_wo_to_awaiting() -> None:
    stats = compute_money_stats(
        [_wo(sc_invoice_status="Open", sc_invoice_total="312.50", nte=400)],
        now=NOW,
    )
    assert stats.awaiting_total == "312.50"
    assert stats.awaiting_count == 1
    assert stats.awaiting_unknown_count == 0
    assert stats.unbilled_unpriced_count == 0


def test_awaiting_falls_back_to_brenk_total() -> None:
    stats = compute_money_stats(
        [_wo(sc_invoice_status="Approved", labor=100, material=0, markup=100)],
        now=NOW,
    )
    assert stats.awaiting_total == "200.00"
    assert stats.awaiting_unknown_count == 0


def test_awaiting_unknown_amount_counted_not_summed() -> None:
    stats = compute_money_stats([_wo(sc_invoice_status="Open")], now=NOW)
    assert stats.awaiting_count == 1
    assert stats.awaiting_unknown_count == 1
    assert stats.awaiting_total == "0.00"


def test_legacy_invoiced_without_synced_invoice_excluded() -> None:
    # Pre-webhook history: INVOICED in SC, nothing synced. Almost all
    # long since paid — must not show up as "awaiting payment".
    stats = compute_money_stats([_wo(primary="INVOICED", extended=None, nte=300)], now=NOW)
    assert stats.awaiting_count == 0
    assert stats.unbilled_priced_count == 0
    assert stats.unbilled_unpriced_count == 0


def test_paid_this_month_with_profit() -> None:
    paid_at = datetime(2026, 6, 10, 18, 0, tzinfo=UTC)
    stats = compute_money_stats(
        [
            _wo(
                primary="INVOICED",
                extended=None,
                labor=100,
                material=50,
                markup=80,
                sc_invoice_total="270.00",
                brenk_paid_at=paid_at,
            )
        ],
        now=NOW,
    )
    assert stats.paid_month_count == 1
    assert stats.paid_month_total == "270.00"
    assert stats.paid_month_profit == "120.00"  # 270 - 150 cost


def test_paid_last_month_excluded_from_all_buckets() -> None:
    paid_at = datetime(2026, 5, 20, tzinfo=UTC)
    stats = compute_money_stats(
        [_wo(primary="INVOICED", extended=None, brenk_paid_at=paid_at)],
        now=NOW,
    )
    assert stats.paid_month_count == 0
    assert stats.awaiting_count == 0


def test_month_boundary_uses_business_timezone() -> None:
    # 2026-06-01 03:00 UTC is still May 31 in America/Chicago (CDT, UTC-5).
    paid_at = datetime(2026, 6, 1, 3, 0, tzinfo=UTC)
    stats = compute_money_stats([_wo(brenk_paid_at=paid_at)], now=NOW)
    assert stats.paid_month_count == 0


def test_sc_paid_status_excludes_from_awaiting() -> None:
    stats = compute_money_stats([_wo(sc_invoice_status="Paid", sc_invoice_total="100.00")], now=NOW)
    assert stats.awaiting_count == 0
    # No paid timestamp -> can't place it in a month either.
    assert stats.paid_month_count == 0


def test_rejected_invoice_in_no_bucket() -> None:
    stats = compute_money_stats([_wo(sc_invoice_status="Rejected", nte=250)], now=NOW)
    assert stats.awaiting_count == 0
    assert stats.unbilled_unpriced_count == 0
