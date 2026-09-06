"""Turnaround-deadline classification for CubeSmart work orders.

CubeSmart expects a 3-5 day turnaround on most WOs, and SC already
encodes the expectation: `scheduled_date` is call_date + 3-5 days on
nearly every WO and gets re-written when a job is legitimately
rescheduled (proposal approved, parts on order, ...). So the deadline
is fully derived — no manual tagging, no schema change:

    deadline = scheduled_date, else call_date + FALLBACK_DAYS

A WO is "at risk" while the work itself is unfinished
(primary_status OPEN / IN PROGRESS). COMPLETED WOs met their
turnaround; the invoice pipeline owns them from there.

Urgency buckets:

    overdue   deadline is in the past
    due_soon  deadline within DUE_SOON_DAYS (2 days of runway is the
              minimum useful warning on a 3-5 day total turnaround)
    ok        deadline further out

The digest email and the dashboard split at-risk WOs into two
sections by who owes the next move:

    needs_action          Daryl's move (WAITING FOR QUOTE, DISPATCH
                          CONFIRMED, INCOMPLETE, PARTS ON ORDER, ...)
    waiting_on_cubesmart  blocked on the client (WAITING FOR APPROVAL
                          = proposal sent, CubeSmart hasn't approved)

Like pipeline.py, this module is the single source of truth: the WO
list endpoint, the dashboard counts, and the daily digest task all
consult the same definitions, so a tile count and the filtered list
it links to are guaranteed to match. The Python functions exist for
testability + per-row enrichment; the SQL clauses exist for
production filtering. They must stay in sync — any edit to one needs
a matching edit to the other.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import ColumnElement, false, func, or_

from app.models.work_order import WorkOrder

# Deadline fallback when SC never set a scheduled_date: the long end
# of CubeSmart's expected turnaround, counted from intake.
FALLBACK_DAYS = 5

# "Due soon" horizon. 1 day gives Daryl no runway to chase a quote or
# a sub-vendor on a 3-5 day turnaround; 2 means a WO due Friday first
# appears in Wednesday morning's digest.
DUE_SOON_DAYS = 2

# Work not yet complete — the only statuses where the turnaround
# clock is still running.
AT_RISK_PRIMARY_STATUSES: tuple[str, ...] = ("OPEN", "IN PROGRESS")

# Extended status meaning "blocked on CubeSmart, not on Brenk":
# a proposal was sent and the client hasn't approved it yet.
WAITING_ON_CLIENT_EXTENDED = "WAITING FOR APPROVAL"

# ?deadline= filter vocabulary. at_risk = overdue + due_soon.
DEADLINE_FILTER_KEYS: tuple[str, ...] = ("at_risk", "overdue", "due_soon")


def is_at_risk_status(primary_status: str | None) -> bool:
    """Is the turnaround clock still running for this primary status?"""
    return (primary_status or "").upper() in AT_RISK_PRIMARY_STATUSES


def deadline_for(
    scheduled_date: datetime | None,
    call_date: datetime | None,
) -> datetime | None:
    """The WO's turnaround deadline: scheduled_date, else call_date + 5d.

    None when both inputs are NULL — such WOs are excluded from
    deadline tracking everywhere (rare enough not to warrant a
    synthetic deadline).
    """
    if scheduled_date is not None:
        return scheduled_date
    if call_date is not None:
        return call_date + timedelta(days=FALLBACK_DAYS)
    return None


def classify_urgency(deadline: datetime | None, now: datetime) -> str | None:
    """Bucket a deadline: 'overdue' | 'due_soon' | 'ok' | None.

    Only meaningful for at-risk statuses — callers gate on
    `is_at_risk_status()` first.
    """
    if deadline is None:
        return None
    if deadline < now:
        return "overdue"
    if deadline <= now + timedelta(days=DUE_SOON_DAYS):
        return "due_soon"
    return "ok"


def days_past_deadline(deadline: datetime, now: datetime) -> float:
    """Signed days relative to the deadline: positive = overdue.

    One number drives both renderings — "Overdue 12d" (positive) and
    "Due in 2d" (negative).
    """
    return (now - deadline).total_seconds() / 86400


def section_for(extended_status: str | None) -> str:
    """Which digest section owns this WO: who has the next move?

    An OPEN WO with no extended status is Daryl's move (accept or
    decline), so the default is needs_action.
    """
    if (extended_status or "").upper() == WAITING_ON_CLIENT_EXTENDED:
        return "waiting_on_cubesmart"
    return "needs_action"


def deadline_expr() -> ColumnElement[datetime]:
    """SQL equivalent of `deadline_for()` over the work_orders columns.

    COALESCE of two NULLs yields NULL, which every comparison in
    `deadline_filter_clauses` excludes — matching the Python None.
    """
    return func.coalesce(
        WorkOrder.scheduled_date,
        WorkOrder.call_date + timedelta(days=FALLBACK_DAYS),
    )


def deadline_filter_clauses(key: str) -> list[ColumnElement[bool]]:
    """SQLAlchemy WHERE clauses selecting WOs in the given urgency bucket.

    Must stay byte-for-byte equivalent to `is_at_risk_status()` +
    `classify_urgency()` so the dashboard counts and the WO list rows
    agree for any key. Returns a list of clauses to be ANDed by the
    caller. Unknown key matches nothing — better an empty list than a
    silent fall-through to "all WOs".
    """
    now = datetime.now(UTC)
    deadline = deadline_expr()
    horizon = now + timedelta(days=DUE_SOON_DAYS)

    base: list[ColumnElement[bool]] = [
        WorkOrder.primary_status.in_(AT_RISK_PRIMARY_STATUSES),
        # Exclude WOs deleted in SC (reconcile marked them) — their local
        # status is frozen and meaningless; they were phantom "overdue".
        WorkOrder.brenk_sc_deleted_at.is_(None),
        # Explicit guard: a WO with neither date has no deadline. The
        # NULL COALESCE would exclude it anyway; this documents intent.
        or_(
            WorkOrder.scheduled_date.is_not(None),
            WorkOrder.call_date.is_not(None),
        ),
    ]

    if key == "overdue":
        return [*base, deadline < now]
    if key == "due_soon":
        return [*base, deadline >= now, deadline <= horizon]
    if key == "at_risk":
        return [*base, deadline <= horizon]
    return [false()]
