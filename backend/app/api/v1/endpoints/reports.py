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

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db.session import get_async_db
from app.models.work_order import WorkOrder
from app.schemas.reports import ReportsSummary
from app.services.reports import build_reports_summary

router = APIRouter()


@router.get("/summary", response_model=ReportsSummary)
async def get_reports_summary(
    session: Annotated[AsyncSession, Depends(get_async_db)],
) -> ReportsSummary:
    """Return markup/spend analytics across all marked-up work orders."""
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
    return build_reports_summary(rows)
