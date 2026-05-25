"""Pipeline-funnel stage classification + aggregation.

Maps each work order to one of the lifecycle stages Daryl actually
operates in (per CLAUDE.md's "Lifecycle stages" table) and computes
the counts + avg age the dashboard needs.

The stage ladder, in order:

  pending_acceptance  IN PROGRESS / WAITING FOR APPROVAL
  dispatched          IN PROGRESS / not waiting (Brenk-vendor optional)
  work_complete       COMPLETED   / PENDING CONFIRMATION
  ready_to_invoice    COMPLETED   / CONFIRMED or NOT INVOICED
  invoiced            INVOICED    / any

`CANCELED` and `NO CHARGE` (both nested under COMPLETED) are terminal
and live outside the pipeline — they don't appear as a stage.

**Dispatched + Vendor-assigned are merged** (2026-05-21). In Daryl's
current workflow, accepting an SC dispatch and texting a sub-vendor
happen in the same sitting — splitting them as separate tiles created
a "stage" Daryl never operationally occupies. When we add Twilio in
Phase 3 ("vendor notified" becomes a meaningful timestamp distinct
from "vendor assigned"), we can re-introduce the split.

This module is the **single source of truth** for what defines each
stage. Both the dashboard counts (via `classify()`) and the WO list
endpoint (via `stage_filter_clauses()`) consult the same definitions
so the count on a tile and the row count on the resulting list page
are guaranteed to match.

The Python `classify()` exists for testability without a database;
the SQL clauses exist for production filtering. They must stay in
sync — any edit to one needs a matching edit to the other.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import ColumnElement, false, or_

from app.models.work_order import WorkOrder


# Stage keys are stable identifiers used by the API + frontend. The
# `label` is the human-readable text shown on the tile. `color` matches
# the SC palette Daryl already lives in (see CLAUDE.md). `stuck_days`
# is the threshold past which a WO in this stage is "stuck" — None
# means the stage is terminal and stuck doesn't apply.
@dataclass(frozen=True)
class StageSpec:
    key: str
    label: str
    color: str  # 'pink' | 'yellow' | 'orange' | 'green' | 'emerald' | 'gray'
    icon: str | None  # 'user' | 'chat' | 'money' | 'check' | None
    stuck_days: int | None


# Order matters: this is the left-to-right order on the dashboard.
STAGES: tuple[StageSpec, ...] = (
    StageSpec(
        key="pending_acceptance",
        label="Pending acceptance",
        color="pink",
        icon=None,
        stuck_days=1,
    ),
    StageSpec(
        key="dispatched",
        label="Dispatched",
        color="yellow",
        icon="user",
        stuck_days=3,
    ),
    StageSpec(
        key="work_complete",
        label="Work complete · awaiting store",
        color="orange",
        icon=None,
        stuck_days=7,
    ),
    StageSpec(
        key="ready_to_invoice",
        label="Ready to invoice",
        color="green",
        icon="money",
        stuck_days=3,
    ),
    StageSpec(
        key="invoiced",
        label="Invoiced",
        color="emerald",
        icon="check",
        stuck_days=None,
    ),
)

STAGE_BY_KEY: dict[str, StageSpec] = {s.key: s for s in STAGES}


def classify(
    primary_status: str,
    extended_status: str | None,
    has_vendor: bool,  # kept for forward-compat; unused after merge
) -> str | None:
    """Map a WO's status triple to a pipeline stage key.

    Returns None for WOs that aren't in the pipeline (terminal states
    like CANCELED / NO CHARGE, or any status we don't recognize yet).

    `has_vendor` is no longer consulted (dispatched + vendor_assigned
    were merged 2026-05-21) but is kept in the signature so callers
    don't need to change when we re-introduce the distinction in a
    later phase.
    """
    del has_vendor  # explicitly unused; see docstring

    p = (primary_status or "").upper()
    e = (extended_status or "").upper()

    if p == "INVOICED":
        return "invoiced"

    if p == "COMPLETED":
        if e in {"CANCELED", "NO CHARGE"}:
            return None  # terminal, not in pipeline
        if e == "PENDING CONFIRMATION":
            return "work_complete"
        # CONFIRMED, NOT INVOICED, and any other "completed but not
        # cancelled" variant -> Sue should be picking this up.
        return "ready_to_invoice"

    if p == "IN PROGRESS":
        if e == "WAITING FOR APPROVAL":
            return "pending_acceptance"
        return "dispatched"

    # Unknown primary status — surface in logs upstream; here we just
    # exclude it so the funnel doesn't grow random tiles.
    return None


def stage_filter_clauses(stage_key: str) -> list[ColumnElement[bool]]:
    """SQLAlchemy WHERE clauses that select WOs in the given stage.

    Must stay byte-for-byte equivalent to `classify()` so the dashboard
    tile count and the WO list row count agree for any stage key.
    Returns a list of clauses to be ANDed together by the caller.

    Unknown stage_key returns a clause that matches nothing — better
    to show an empty list than to silently fall through to "all WOs".
    """
    if stage_key == "pending_acceptance":
        return [
            WorkOrder.primary_status == "IN PROGRESS",
            WorkOrder.extended_status == "WAITING FOR APPROVAL",
        ]
    if stage_key == "dispatched":
        return [
            WorkOrder.primary_status == "IN PROGRESS",
            or_(
                WorkOrder.extended_status != "WAITING FOR APPROVAL",
                WorkOrder.extended_status.is_(None),
            ),
        ]
    if stage_key == "work_complete":
        return [
            WorkOrder.primary_status == "COMPLETED",
            WorkOrder.extended_status == "PENDING CONFIRMATION",
        ]
    if stage_key == "ready_to_invoice":
        return [
            WorkOrder.primary_status == "COMPLETED",
            WorkOrder.extended_status.notin_(["CANCELED", "NO CHARGE", "PENDING CONFIRMATION"]),
        ]
    if stage_key == "invoiced":
        return [WorkOrder.primary_status == "INVOICED"]
    return [false()]


def is_stuck(stage_key: str, sc_updated_date: datetime | None) -> bool:
    """Has this WO been sitting in its current stage past the threshold?

    We use `sc_updated_date` as a proxy for "how long has it been like
    this." It's not perfect — Brenk-side actions (assigning a vendor
    in our app) don't bump it — but for v1 it's good enough and
    doesn't need a status_history join on every dashboard render.
    """
    if sc_updated_date is None:
        return False
    spec = STAGE_BY_KEY.get(stage_key)
    if spec is None or spec.stuck_days is None:
        return False
    age = (datetime.now(UTC) - sc_updated_date).total_seconds() / 86400
    return age > spec.stuck_days


def age_days(sc_updated_date: datetime | None) -> float | None:
    """Days since last SC update. None if we don't know."""
    if sc_updated_date is None:
        return None
    return (datetime.now(UTC) - sc_updated_date).total_seconds() / 86400
