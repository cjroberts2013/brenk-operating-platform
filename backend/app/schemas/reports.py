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


class MarkupByCategory(BaseModel):
    """Profit + markup for one Brenk job category (marked-up jobs only)."""

    category: str
    jobs_with_markup: int
    avg_actual_markup_percent: float | None
    total_vendor_cost: str
    total_margin: str


class CategoryOverview(BaseModel):
    """Volume + billed revenue for one job category — populated from
    categorization + SC invoices, independent of the markup helper.

    `billed`/`paid` are sums of linked SC invoice totals (what the client
    was billed / has paid). This answers "how much is this category making"
    in revenue terms even before vendor costs are entered."""

    category: str
    jobs: int  # total WOs in this category
    invoiced_jobs: int  # WOs that reached INVOICED status
    billed: str  # sum of non-void invoice totals
    paid: str  # sum of paid invoice totals


class ReportsCoverage(BaseModel):
    """How much of the data needed for profit analytics actually exists yet.
    Drives the "price more jobs to unlock profit" nudge."""

    invoiced_jobs: int  # WOs that have been invoiced
    priced_jobs: int  # WOs with a markup % or a direct total entered


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
    markup_by_category: list[MarkupByCategory]
    vendor_spend: list[VendorSpend]
    # Revenue/volume by category + data-coverage. Populated by the endpoint
    # (from invoices + WO counts), so they default empty for the pure
    # markup-aggregation path / tests.
    category_overview: list[CategoryOverview] = []
    coverage: ReportsCoverage | None = None
