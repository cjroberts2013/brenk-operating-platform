"""Dashboard money stats — DB-free aggregation over work-order rows.

Answers the three dollar questions the funnel's counts can't:

  1. Unbilled work   — completed + store-confirmed WOs with no SC
                       invoice yet. Priced ones sum Brenk's exact total
                       bill; unpriced ones sum NTE as a ceiling.
  2. Awaiting payment — WOs with an active synced SC invoice that isn't
                       paid yet. Deliberately limited to invoices we
                       actually have webhook data for: legacy WOs that
                       went to INVOICED before webhook sync existed have
                       no amount and are almost all long since paid —
                       counting them would drown the number in noise.
  3. Paid this month — WOs whose effective paid date falls in the
                       current month (business timezone), plus the
                       profit on the ones whose vendor costs we know.

Bucket membership mirrors the invoice-tab filters in
`app/api/v1/endpoints/work_orders.py` (ready_to_markup/marked_up for
unbilled, sent for awaiting) and stage membership mirrors
`app/services/pipeline.py` `classify()` — keep them in sync.

Pure functions over WorkOrder-shaped objects so the math is unit-
testable without a database, same pattern as `app/services/reports.py`.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from app.models.work_order import WorkOrder
from app.services.pipeline import classify

# Where Brenk operates; month boundaries for "paid this month" follow
# this clock, not UTC.
BUSINESS_TZ = ZoneInfo("America/Chicago")

# Same set as the invoice-tab logic in endpoints/work_orders.py:
# invoice exists in SC and is moving toward payment.
ACTIVE_INVOICE_STATUSES = frozenset({"Open", "Approved", "On Hold", "Reviewed", "Disputed"})

_TWO_PLACES = Decimal("0.01")


class MoneyStats(BaseModel):
    """Dollar totals for the dashboard stat band. Decimal amounts are
    serialized as strings, matching the WO money fields."""

    # Unbilled: ready-to-invoice WOs with no open/terminal SC invoice.
    unbilled_priced_total: str  # exact Brenk total bills
    unbilled_priced_count: int
    unbilled_unpriced_nte_total: str  # NTE ceiling for not-yet-priced
    unbilled_unpriced_count: int

    # Awaiting payment: active synced SC invoice, not paid.
    awaiting_total: str
    awaiting_count: int
    awaiting_unknown_count: int  # active invoice but no amount on record

    # Paid in the current business-timezone month.
    paid_month_total: str
    paid_month_count: int
    paid_month_profit: str | None  # None when no vendor costs known
    month_label: str  # e.g. "June" — so the tile names the month


def _q(amount: Decimal) -> str:
    return str(amount.quantize(_TWO_PLACES))


def brenk_total_bill(wo: WorkOrder) -> Decimal | None:
    """(labor + material) * (1 + markup/100), or None if not fully priced."""
    if wo.brenk_markup_percent is None:
        return None
    cost = (wo.brenk_labor_cost or Decimal(0)) + (wo.brenk_material_cost or Decimal(0))
    if cost <= 0:
        return None
    return cost * (1 + wo.brenk_markup_percent / 100)


def _billed_amount(wo: WorkOrder) -> Decimal | None:
    """Best known invoiced-to-client amount: SC's actual invoice total
    when synced, else Brenk's computed total bill."""
    if wo.sc_invoice_total is not None:
        return wo.sc_invoice_total
    return brenk_total_bill(wo)


def _is_paid(wo: WorkOrder) -> bool:
    return (
        wo.brenk_paid_at is not None or wo.sc_paid_at is not None or wo.sc_invoice_status == "Paid"
    )


def _no_open_invoice(wo: WorkOrder) -> bool:
    """No SC invoice exists for this WO yet (mirrors the NULL-safe
    `no_open_invoice` clause in the invoice-tab filters)."""
    s = wo.sc_invoice_status
    if s is not None and (s in ACTIVE_INVOICE_STATUSES or s in {"Rejected", "Paid"}):
        return False
    # Legacy: INVOICED in SC before webhook sync existed.
    return not (wo.primary_status == "INVOICED" and s is None)


def compute_money_stats(rows: list[WorkOrder], now: datetime | None = None) -> MoneyStats:
    """Aggregate the dashboard money stats from already-loaded WO rows."""
    local_now = (now or datetime.now(BUSINESS_TZ)).astimezone(BUSINESS_TZ)
    month_start = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    unbilled_priced = Decimal(0)
    unbilled_priced_n = 0
    unbilled_nte = Decimal(0)
    unbilled_unpriced_n = 0

    awaiting = Decimal(0)
    awaiting_n = 0
    awaiting_unknown_n = 0

    paid_month = Decimal(0)
    paid_month_n = 0
    paid_month_profit: Decimal | None = None

    for wo in rows:
        paid = _is_paid(wo)

        # ---- Paid this month ----
        paid_at = wo.brenk_paid_at or wo.sc_paid_at
        if paid_at is not None and paid_at.astimezone(BUSINESS_TZ) >= month_start:
            paid_month_n += 1
            amount = _billed_amount(wo)
            if amount is not None:
                paid_month += amount
                cost = (wo.brenk_labor_cost or Decimal(0)) + (wo.brenk_material_cost or Decimal(0))
                if cost > 0:
                    paid_month_profit = (paid_month_profit or Decimal(0)) + (amount - cost)
            continue  # paid WOs belong to no other bucket

        if paid:
            continue

        # ---- Awaiting payment: active synced SC invoice ----
        if wo.sc_invoice_status in ACTIVE_INVOICE_STATUSES:
            awaiting_n += 1
            amount = _billed_amount(wo)
            if amount is None:
                awaiting_unknown_n += 1
            else:
                awaiting += amount
            continue

        # ---- Unbilled: ready to invoice, no SC invoice yet ----
        stage = classify(wo.primary_status, wo.extended_status, wo.assigned_vendor_id is not None)
        if stage == "ready_to_invoice" and _no_open_invoice(wo):
            total = brenk_total_bill(wo)
            if total is not None:
                unbilled_priced += total
                unbilled_priced_n += 1
            else:
                unbilled_unpriced_n += 1
                if wo.nte is not None:
                    unbilled_nte += wo.nte

    return MoneyStats(
        unbilled_priced_total=_q(unbilled_priced),
        unbilled_priced_count=unbilled_priced_n,
        unbilled_unpriced_nte_total=_q(unbilled_nte),
        unbilled_unpriced_count=unbilled_unpriced_n,
        awaiting_total=_q(awaiting),
        awaiting_count=awaiting_n,
        awaiting_unknown_count=awaiting_unknown_n,
        paid_month_total=_q(paid_month),
        paid_month_count=paid_month_n,
        paid_month_profit=_q(paid_month_profit) if paid_month_profit is not None else None,
        month_label=local_now.strftime("%B"),
    )
