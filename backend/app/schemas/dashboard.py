"""Pydantic schemas for the dashboard pipeline-funnel endpoint."""

from datetime import datetime

from pydantic import BaseModel

from app.schemas.work_order import LocationRef, TradeRef, VendorRef
from app.services.money import MoneyStats


class PipelineStage(BaseModel):
    """One stage in the lifecycle funnel."""

    key: str
    label: str
    color: str
    icon: str | None
    count: int
    avg_age_days: float | None
    stuck_count: int
    stuck_threshold_days: int | None


class StuckWorkOrder(BaseModel):
    """A work order currently overdue for its stage."""

    id: int
    sc_work_order_id: int
    sc_number: str
    primary_status: str
    extended_status: str | None
    stage_key: str
    stage_label: str
    age_days: float
    overdue_by_days: float  # age - stage threshold

    trade: TradeRef | None
    location: LocationRef | None
    assigned_vendor: VendorRef | None

    nte: str | None
    scheduled_date: datetime | None
    sc_updated_date: datetime | None


class DeadlineWatch(BaseModel):
    """Turnaround-deadline counts for the Deadline watch panel.

    Same definitions as the WO list's `?deadline=` filter (see
    app.services.deadlines), so each count equals the row count of the
    list it links to. The section counts split at_risk (= overdue +
    due_soon) by who owes the next move.
    """

    overdue_count: int
    due_soon_count: int
    needs_action_count: int
    waiting_on_cubesmart_count: int
    due_soon_window_days: int


class DashboardPipeline(BaseModel):
    """The full dashboard payload — stage tiles + the stuck list."""

    stages: list[PipelineStage]
    stuck: list[StuckWorkOrder]
    total_open: int  # all non-terminal, non-invoiced WOs
    total_invoiced: int
    money: MoneyStats
    deadline_watch: DeadlineWatch
