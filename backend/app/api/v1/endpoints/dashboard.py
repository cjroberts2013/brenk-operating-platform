"""Dashboard pipeline-funnel endpoint.

One endpoint, `GET /api/v1/dashboard/pipeline`, returns everything the
home page needs: per-stage counts + avg age + stuck count, the list
of stuck WOs (top 20, most overdue first), and the top-line open vs
invoiced split.

At Brenk's volume (~341 WOs total, ~100 in the active pipeline at any
given moment), classifying in Python after a minimal SQL projection
is plenty fast and keeps the stage logic centralized in
`app/services/pipeline.py`. If volume grows 10x we can revisit with a
CASE-based SQL group-by.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db.session import get_async_db
from app.models.work_order import WorkOrder
from app.schemas.dashboard import (
    DashboardPipeline,
    PipelineStage,
    StuckWorkOrder,
)
from app.schemas.work_order import LocationRef, TradeRef, VendorRef
from app.services.pipeline import (
    STAGE_BY_KEY,
    STAGES,
    age_days,
    classify,
    is_stuck,
)

router = APIRouter()


_STUCK_LIST_LIMIT = 20


@router.get("/pipeline", response_model=DashboardPipeline)
async def get_pipeline(
    session: Annotated[AsyncSession, Depends(get_async_db)],
) -> DashboardPipeline:
    """Return the dashboard's pipeline funnel + stuck-WO panel."""
    # Pull every WO with its refs eagerly loaded. We need refs only for
    # the stuck rows but loading them for everyone is cheap at our
    # scale and avoids a second round-trip just to enrich the top 20.
    rows = (
        (
            await session.execute(
                select(WorkOrder).options(
                    joinedload(WorkOrder.trade),
                    joinedload(WorkOrder.location),
                    joinedload(WorkOrder.assigned_vendor),
                )
            )
        )
        .scalars()
        .all()
    )

    # ------------ classify ------------
    # Per-stage: running list of (age_days, wo) for the stuck panel,
    # plus aggregate counts/sums for the tiles.
    per_stage_count: dict[str, int] = {s.key: 0 for s in STAGES}
    per_stage_age_sum: dict[str, float] = {s.key: 0.0 for s in STAGES}
    per_stage_age_n: dict[str, int] = {s.key: 0 for s in STAGES}
    per_stage_stuck_count: dict[str, int] = {s.key: 0 for s in STAGES}
    stuck_candidates: list[tuple[float, WorkOrder, str]] = []

    for wo in rows:
        stage_key = classify(
            wo.primary_status, wo.extended_status, wo.assigned_vendor_id is not None
        )
        if stage_key is None:
            continue

        per_stage_count[stage_key] += 1

        age = age_days(wo.sc_updated_date)
        if age is not None:
            per_stage_age_sum[stage_key] += age
            per_stage_age_n[stage_key] += 1

        if is_stuck(stage_key, wo.sc_updated_date) and age is not None:
            per_stage_stuck_count[stage_key] += 1
            threshold = STAGE_BY_KEY[stage_key].stuck_days or 0
            stuck_candidates.append((age - threshold, wo, stage_key))

    # ------------ tiles ------------
    stages_out = [
        PipelineStage(
            key=s.key,
            label=s.label,
            color=s.color,
            icon=s.icon,
            count=per_stage_count[s.key],
            avg_age_days=(
                per_stage_age_sum[s.key] / per_stage_age_n[s.key]
                if per_stage_age_n[s.key]
                else None
            ),
            stuck_count=per_stage_stuck_count[s.key],
            stuck_threshold_days=s.stuck_days,
        )
        for s in STAGES
    ]

    # ------------ stuck list ------------
    # Most-overdue first, capped at _STUCK_LIST_LIMIT.
    stuck_candidates.sort(key=lambda triple: triple[0], reverse=True)
    stuck_out: list[StuckWorkOrder] = []
    for overdue, wo, stage_key in stuck_candidates[:_STUCK_LIST_LIMIT]:
        stuck_out.append(
            StuckWorkOrder(
                id=wo.id,
                sc_work_order_id=wo.sc_work_order_id,
                sc_number=wo.sc_number,
                primary_status=wo.primary_status,
                extended_status=wo.extended_status,
                stage_key=stage_key,
                stage_label=STAGE_BY_KEY[stage_key].label,
                age_days=age_days(wo.sc_updated_date) or 0.0,
                overdue_by_days=overdue,
                trade=TradeRef.model_validate(wo.trade) if wo.trade else None,
                location=LocationRef.model_validate(wo.location) if wo.location else None,
                assigned_vendor=(
                    VendorRef.model_validate(wo.assigned_vendor) if wo.assigned_vendor else None
                ),
                nte=str(wo.nte) if wo.nte is not None else None,
                scheduled_date=wo.scheduled_date,
                sc_updated_date=wo.sc_updated_date,
            )
        )

    # ------------ top-line counts ------------
    total_invoiced = per_stage_count.get("invoiced", 0)
    total_open = sum(per_stage_count[k] for k in per_stage_count if k != "invoiced")

    return DashboardPipeline(
        stages=stages_out,
        stuck=stuck_out,
        total_open=total_open,
        total_invoiced=total_invoiced,
    )
