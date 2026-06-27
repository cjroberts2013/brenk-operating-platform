"""Reports summary endpoint.

`GET /api/v1/reports/summary` returns money/markup analytics derived
entirely from the Brenk-confidential markup fields on work orders
(`brenk_labor_cost`, `brenk_material_cost`, `brenk_markup_percent`).

Like the dashboard, we project every WO and aggregate in Python — the
markup math lives in `app/services/reports.py` so it stays unit-testable
and out of the request handler. At Brenk's volume a SQL group-by would
be premature.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db.session import get_async_db
from app.models.invoice import Invoice
from app.models.work_order import Location, Vendor, WorkOrder, WoVendorAssignment
from app.schemas.reports import (
    CategoryOverview,
    PayablesResponse,
    ReportsCoverage,
    ReportsSummary,
    VendorPayable,
)
from app.services.reports import build_reports_summary

router = APIRouter()

# Invoice statuses that don't count as billed revenue.
_NON_BILLED_STATUSES = ("Void", "Rejected")


def _money(value: Decimal | None) -> str:
    return f"{(value or Decimal(0)).quantize(Decimal('0.01'))}"


@router.get("/summary", response_model=ReportsSummary)
async def get_reports_summary(
    session: Annotated[AsyncSession, Depends(get_async_db)],
) -> ReportsSummary:
    """Markup/profit analytics (from the markup helper) + revenue/volume by
    category (from categorization + SC invoices) + data coverage."""
    rows = (
        (
            await session.execute(
                select(WorkOrder).options(
                    joinedload(WorkOrder.trade),
                    joinedload(WorkOrder.assigned_vendor),
                )
            )
        )
        .scalars()
        .all()
    )
    summary = build_reports_summary(rows)

    # --- volume by category (all categorized WOs) ---
    volume = {
        cat: (jobs, invoiced)
        for cat, jobs, invoiced in (
            await session.execute(
                select(
                    WorkOrder.brenk_category,
                    func.count(WorkOrder.id),
                    func.count(WorkOrder.id).filter(WorkOrder.primary_status == "INVOICED"),
                )
                .where(WorkOrder.brenk_category.is_not(None))
                .group_by(WorkOrder.brenk_category)
            )
        ).all()
    }

    # --- billed/paid revenue by category (linked SC invoices) ---
    revenue = {
        cat: (billed, paid)
        for cat, billed, paid in (
            await session.execute(
                select(
                    WorkOrder.brenk_category,
                    func.sum(Invoice.invoice_total).filter(
                        Invoice.status.notin_(_NON_BILLED_STATUSES)
                    ),
                    func.sum(Invoice.invoice_total).filter(Invoice.status == "Paid"),
                )
                .select_from(Invoice)
                .join(WorkOrder, WorkOrder.sc_work_order_id == Invoice.wo_tracking_number)
                .where(
                    WorkOrder.brenk_category.is_not(None),
                    Invoice.invoice_total.is_not(None),
                )
                .group_by(WorkOrder.brenk_category)
            )
        ).all()
    }

    overview = [
        CategoryOverview(
            category=cat,
            jobs=jobs,
            invoiced_jobs=invoiced,
            billed=_money(revenue.get(cat, (None, None))[0]),
            paid=_money(revenue.get(cat, (None, None))[1]),
        )
        for cat, (jobs, invoiced) in volume.items()
    ]
    # Most revenue first, then most jobs — surfaces the money-makers up top.
    overview.sort(key=lambda c: (Decimal(c.billed), c.jobs), reverse=True)
    summary.category_overview = overview

    # --- data coverage (for the "price more jobs" nudge) ---
    invoiced_jobs, priced_jobs = (
        await session.execute(
            select(
                func.count(WorkOrder.id).filter(WorkOrder.primary_status == "INVOICED"),
                func.count(WorkOrder.id).filter(
                    or_(
                        WorkOrder.brenk_markup_percent.is_not(None),
                        WorkOrder.brenk_total_override.is_not(None),
                    )
                ),
            )
        )
    ).one()
    summary.coverage = ReportsCoverage(invoiced_jobs=invoiced_jobs, priced_jobs=priced_jobs)

    return summary


@router.get("/payables", response_model=PayablesResponse)
async def get_payables(
    session: Annotated[AsyncSession, Depends(get_async_db)],
) -> PayablesResponse:
    """Outstanding sub-vendor payouts — what Brenk still owes, with the
    client-already-paid cases flagged (and surfaced first)."""
    rows = (
        await session.execute(
            select(WoVendorAssignment, WorkOrder, Vendor, Location)
            .join(WorkOrder, WorkOrder.id == WoVendorAssignment.work_order_id)
            .join(Vendor, Vendor.id == WoVendorAssignment.vendor_id)
            .outerjoin(Location, Location.id == WorkOrder.location_id)
            .where(
                WoVendorAssignment.paid_to_vendor_at.is_(None),
                or_(
                    WoVendorAssignment.labor_cost.is_not(None),
                    WoVendorAssignment.material_cost.is_not(None),
                ),
            )
        )
    ).all()

    items: list[VendorPayable] = []
    total = Decimal(0)
    total_client_paid = Decimal(0)
    for assignment, wo, vendor, location in rows:
        payout = (assignment.labor_cost or Decimal(0)) + (assignment.material_cost or Decimal(0))
        if payout <= 0:
            continue
        client_paid = wo.brenk_paid_at is not None
        total += payout
        if client_paid:
            total_client_paid += payout
        items.append(
            VendorPayable(
                work_order_id=wo.id,
                sc_number=wo.sc_number,
                vendor_id=vendor.id,
                vendor_name=vendor.name,
                location=location.name if location else None,
                payout=_money(payout),
                client_paid=client_paid,
            )
        )

    # Urgent (client already paid) first, then largest payout.
    items.sort(key=lambda i: (i.client_paid, Decimal(i.payout)), reverse=True)

    return PayablesResponse(
        items=items,
        total_outstanding=_money(total),
        total_client_paid=_money(total_client_paid),
    )
