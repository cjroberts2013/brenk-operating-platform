"""Tests for the turnaround-deadline classification service."""

from datetime import UTC, datetime, timedelta

from app.services.deadlines import (
    DUE_SOON_DAYS,
    FALLBACK_DAYS,
    classify_urgency,
    days_past_deadline,
    deadline_filter_clauses,
    deadline_for,
    is_at_risk_status,
    section_for,
)

NOW = datetime(2026, 7, 3, 12, 0, tzinfo=UTC)


# --------------------------- deadline_for ---------------------------


def test_scheduled_date_wins() -> None:
    scheduled = NOW + timedelta(days=3)
    called = NOW - timedelta(days=10)
    assert deadline_for(scheduled, called) == scheduled


def test_fallback_is_call_date_plus_five_days() -> None:
    called = NOW - timedelta(days=1)
    assert deadline_for(None, called) == called + timedelta(days=FALLBACK_DAYS)


def test_both_null_means_no_deadline() -> None:
    assert deadline_for(None, None) is None


# --------------------------- classify_urgency ---------------------------


def test_past_deadline_is_overdue() -> None:
    assert classify_urgency(NOW - timedelta(seconds=1), NOW) == "overdue"


def test_deadline_exactly_now_is_due_soon() -> None:
    # Boundary: not yet past, so it's the operator's last window.
    assert classify_urgency(NOW, NOW) == "due_soon"


def test_within_horizon_is_due_soon() -> None:
    assert classify_urgency(NOW + timedelta(days=DUE_SOON_DAYS), NOW) == "due_soon"


def test_beyond_horizon_is_ok() -> None:
    assert classify_urgency(NOW + timedelta(days=DUE_SOON_DAYS, seconds=1), NOW) == "ok"


def test_no_deadline_is_none() -> None:
    assert classify_urgency(None, NOW) is None


# --------------------------- days_past_deadline ---------------------------


def test_overdue_is_positive() -> None:
    assert days_past_deadline(NOW - timedelta(days=12), NOW) == 12.0


def test_time_remaining_is_negative() -> None:
    assert days_past_deadline(NOW + timedelta(days=2), NOW) == -2.0


# --------------------------- is_at_risk_status ---------------------------


def test_open_and_in_progress_are_at_risk() -> None:
    assert is_at_risk_status("OPEN")
    assert is_at_risk_status("IN PROGRESS")
    assert is_at_risk_status("in progress")  # case-insensitive


def test_completed_invoiced_and_none_are_not_at_risk() -> None:
    assert not is_at_risk_status("COMPLETED")
    assert not is_at_risk_status("INVOICED")
    assert not is_at_risk_status(None)


# --------------------------- section_for ---------------------------


def test_waiting_for_approval_is_waiting_on_cubesmart() -> None:
    assert section_for("WAITING FOR APPROVAL") == "waiting_on_cubesmart"
    assert section_for("waiting for approval") == "waiting_on_cubesmart"


def test_everything_else_needs_action() -> None:
    assert section_for("WAITING FOR QUOTE") == "needs_action"
    assert section_for("DISPATCH CONFIRMED") == "needs_action"
    assert section_for(None) == "needs_action"  # bare OPEN WO — Daryl's move


# --------------------------- SQL clauses ---------------------------


def test_known_keys_produce_clauses() -> None:
    for key in ("at_risk", "overdue", "due_soon"):
        clauses = deadline_filter_clauses(key)
        # base status filter + null guard + at least one deadline bound
        assert len(clauses) >= 3


def test_unknown_key_matches_nothing() -> None:
    clauses = deadline_filter_clauses("nonsense")
    assert len(clauses) == 1
    assert str(clauses[0]) == "false"
