"""Unit tests for stuck-eligibility (pure, no DB).

Per Daryl (2026-09-06): a WO marked COMPLETED in SC must never appear in
the dashboard's "Stuck right now" panel — the completed→invoice workflow
lives on the Invoices page. So the two COMPLETED pipeline stages
(work_complete, ready_to_invoice) are not stuck-eligible.
"""

from datetime import UTC, datetime, timedelta

from app.services.pipeline import STAGE_BY_KEY, classify, is_stuck

LONG_AGO = datetime.now(UTC) - timedelta(days=365)


def test_completed_stages_are_not_stuck_eligible() -> None:
    assert STAGE_BY_KEY["work_complete"].stuck_days is None
    assert STAGE_BY_KEY["ready_to_invoice"].stuck_days is None
    # Even a year-old completed WO is not "stuck".
    assert is_stuck("work_complete", LONG_AGO) is False
    assert is_stuck("ready_to_invoice", LONG_AGO) is False


def test_completed_wo_classifies_but_is_not_stuck() -> None:
    # A COMPLETED/CONFIRMED WO is still a real pipeline stage (ready_to_invoice)
    # so it counts in the funnel + shows on the Invoices page — it just
    # doesn't count as stuck.
    stage = classify("COMPLETED", "CONFIRMED", has_vendor=True)
    assert stage == "ready_to_invoice"
    assert is_stuck(stage, LONG_AGO) is False


def test_pre_completion_stages_still_stuck_eligible() -> None:
    # The panel still catches pre-completion stalls.
    assert STAGE_BY_KEY["pending_acceptance"].stuck_days == 1
    assert STAGE_BY_KEY["dispatched"].stuck_days == 3
    assert is_stuck("pending_acceptance", LONG_AGO) is True
    assert is_stuck("dispatched", LONG_AGO) is True
