"""Reports aggregation — pure, DB-free markup/spend analytics.

`build_reports_summary` takes an iterable of work orders (with their
`trade` and `assigned_vendor` relationships loaded) and returns the
fully-shaped `ReportsSummary`. Keeping it free of the DB session makes
the markup math unit-testable in isolation; the endpoint is just a
query that feeds this.

A work order contributes only once it has a markup % AND a non-zero
vendor cost — so the payload is empty until Daryl uses the markup
helper on real invoices.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal

from app.models.work_order import WorkOrder
from app.schemas.reports import (
    MarkupByCategory,
    MarkupByTrade,
    ReportsSummary,
    ReportsTotals,
    VendorSpend,
)


def _vendor_subtotal(wo: WorkOrder) -> Decimal:
    """Labor + material, treating an unset side as zero."""
    return (wo.brenk_labor_cost or Decimal(0)) + (wo.brenk_material_cost or Decimal(0))


def _contributes(wo: WorkOrder) -> bool:
    """A WO counts toward reports once it has a markup % and real cost."""
    return wo.brenk_markup_percent is not None and _vendor_subtotal(wo) > 0


@dataclass
class _Bucket:
    """Running aggregation for a trade or vendor group."""

    jobs: int = 0
    vendor_cost: Decimal = field(default_factory=lambda: Decimal(0))
    margin: Decimal = field(default_factory=lambda: Decimal(0))
    markup_sum: float = 0.0  # sum of actual markup %, for averaging


def _money(value: Decimal) -> str:
    """Serialize a Decimal as a 2-dp string for the frontend."""
    return f"{value.quantize(Decimal('0.01'))}"


def build_reports_summary(work_orders: Iterable[WorkOrder]) -> ReportsSummary:
    """Aggregate markup/spend analytics across the given work orders."""
    total = _Bucket()
    by_trade: dict[int, _Bucket] = defaultdict(_Bucket)
    by_category: dict[str, _Bucket] = defaultdict(_Bucket)
    by_vendor: dict[int, _Bucket] = defaultdict(_Bucket)
    trade_names: dict[int, str] = {}
    trade_defaults: dict[int, float | None] = {}
    vendor_names: dict[int, str] = {}

    for wo in work_orders:
        if not _contributes(wo):
            continue

        subtotal = _vendor_subtotal(wo)
        markup_decimal = wo.brenk_markup_percent
        assert markup_decimal is not None  # guaranteed by _contributes
        markup_pct = float(markup_decimal)
        margin = subtotal * (markup_decimal / Decimal(100))

        total.jobs += 1
        total.vendor_cost += subtotal
        total.margin += margin
        total.markup_sum += markup_pct

        if wo.trade is not None:
            b = by_trade[wo.trade.id]
            b.jobs += 1
            b.vendor_cost += subtotal
            b.margin += margin
            b.markup_sum += markup_pct
            trade_names[wo.trade.id] = wo.trade.name
            trade_defaults[wo.trade.id] = (
                float(wo.trade.default_markup_percent)
                if wo.trade.default_markup_percent is not None
                else None
            )

        if wo.brenk_category:
            c = by_category[wo.brenk_category]
            c.jobs += 1
            c.vendor_cost += subtotal
            c.margin += margin
            c.markup_sum += markup_pct

        if wo.assigned_vendor is not None:
            v = by_vendor[wo.assigned_vendor.id]
            v.jobs += 1
            v.vendor_cost += subtotal
            v.margin += margin
            vendor_names[wo.assigned_vendor.id] = wo.assigned_vendor.name

    # ---- totals ----
    blended = float(total.margin / total.vendor_cost * 100) if total.vendor_cost > 0 else None
    totals = ReportsTotals(
        jobs_with_markup=total.jobs,
        total_vendor_cost=_money(total.vendor_cost),
        total_margin=_money(total.margin),
        total_billed=_money(total.vendor_cost + total.margin),
        blended_markup_percent=round(blended, 1) if blended is not None else None,
    )

    # ---- markup by trade (actual vs. configured default) ----
    markup_by_trade: list[MarkupByTrade] = []
    for trade_id, b in by_trade.items():
        avg_actual = round(b.markup_sum / b.jobs, 1) if b.jobs else None
        default = trade_defaults.get(trade_id)
        delta = (
            round(avg_actual - default, 1)
            if avg_actual is not None and default is not None
            else None
        )
        markup_by_trade.append(
            MarkupByTrade(
                trade_id=trade_id,
                trade_name=trade_names[trade_id],
                default_markup_percent=default,
                jobs_with_markup=b.jobs,
                avg_actual_markup_percent=avg_actual,
                delta_percent=delta,
                total_vendor_cost=_money(b.vendor_cost),
                total_margin=_money(b.margin),
            )
        )
    markup_by_trade.sort(key=lambda m: m.trade_name.lower())

    # ---- markup by category (profit per job type) ----
    markup_by_category = [
        MarkupByCategory(
            category=category,
            jobs_with_markup=b.jobs,
            avg_actual_markup_percent=round(b.markup_sum / b.jobs, 1) if b.jobs else None,
            total_vendor_cost=_money(b.vendor_cost),
            total_margin=_money(b.margin),
        )
        for category, b in by_category.items()
    ]
    markup_by_category.sort(key=lambda m: m.category.lower())

    # ---- vendor spend (most spend first) ----
    vendor_spend = [
        VendorSpend(
            vendor_id=vendor_id,
            vendor_name=vendor_names[vendor_id],
            jobs=v.jobs,
            total_vendor_cost=_money(v.vendor_cost),
            total_margin=_money(v.margin),
        )
        for vendor_id, v in by_vendor.items()
    ]
    vendor_spend.sort(key=lambda v: Decimal(v.total_vendor_cost), reverse=True)

    return ReportsSummary(
        totals=totals,
        markup_by_trade=markup_by_trade,
        markup_by_category=markup_by_category,
        vendor_spend=vendor_spend,
    )
