"""Pydantic schemas for the reports summary endpoint.

All money figures are strings (serialized Decimals) so the frontend
formats them itself without float rounding surprises. Markup percents
are floats — they're averages, not money.
"""

from pydantic import BaseModel


class MarkupByTrade(BaseModel):
    """Markup actual-vs-suggested for one trade.

    Answers the open iteration question: is the per-trade default Daryl
    set in Settings actually matching the markup he ends up choosing?
    `jobs_with_markup` is the sample size — a delta off a single job
    means little.
    """

    trade_id: int
    trade_name: str
    default_markup_percent: float | None  # the suggestion configured in Settings
    jobs_with_markup: int
    avg_actual_markup_percent: float | None  # None when jobs_with_markup == 0
    # actual minus default; None when either side is missing
    delta_percent: float | None
    total_vendor_cost: str  # sum of labor + material across the trade's marked-up jobs
    total_margin: str  # sum of (total bill - vendor cost)


class VendorSpend(BaseModel):
    """Spend + margin routed through one vendor (marked-up jobs only)."""

    vendor_id: int
    vendor_name: str
    jobs: int
    total_vendor_cost: str
    total_margin: str


class ReportsTotals(BaseModel):
    """Top-line money figures across every marked-up work order."""

    jobs_with_markup: int
    total_vendor_cost: str  # what Brenk paid sub-vendors
    total_margin: str  # Brenk's markup margin
    total_billed: str  # vendor cost + margin = what the client is billed
    blended_markup_percent: float | None  # total_margin / total_vendor_cost * 100


class ReportsSummary(BaseModel):
    """The full reports payload.

    Everything is derived from the Brenk-confidential markup fields
    (`brenk_labor_cost`, `brenk_material_cost`, `brenk_markup_percent`).
    A work order only contributes once it has a markup % AND a non-zero
    vendor cost entered — so the page is empty until Daryl starts using
    the markup helper on real invoices.
    """

    totals: ReportsTotals
    markup_by_trade: list[MarkupByTrade]
    vendor_spend: list[VendorSpend]
