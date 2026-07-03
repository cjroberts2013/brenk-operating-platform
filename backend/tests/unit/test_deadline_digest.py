"""Tests for the turnaround-deadline digest email builder (pure, no DB)."""

from datetime import UTC, datetime, timedelta

from app.services.deadline_digest import (
    MAX_ROWS_PER_SECTION,
    DigestItem,
    build_digest_email,
    due_label,
)

NOW = datetime(2026, 7, 3, 12, 0, tzinfo=UTC)


def _item(**overrides) -> DigestItem:
    base = dict(
        sc_number="353085818",
        location="CubeSmart 0361",
        extended_status="DISPATCH CONFIRMED",
        deadline=NOW - timedelta(days=12),
        days_past_deadline=12.0,
        urgency="overdue",
        section="needs_action",
        dashboard_url="https://app.brenkfacilityservices.com/work-orders/42",
        sc_url="https://www.servicechannel.com/sc/wo/Workorders/index?id=99",
    )
    base.update(overrides)
    return DigestItem(**base)


# --------------------------- due_label ---------------------------


def test_due_label_buckets() -> None:
    assert due_label(12.4) == "Overdue 12d"
    assert due_label(0.5) == "Due today"
    assert due_label(-0.5) == "Due today"
    assert due_label(-2.0) == "Due in 2d"
    assert due_label(-1.5) == "Due in 2d"


# --------------------------- build_digest_email ---------------------------


def test_subject_counts_by_urgency() -> None:
    items = [
        _item(),
        _item(sc_number="2", urgency="due_soon", days_past_deadline=-1.0),
        _item(sc_number="3", urgency="due_soon", days_past_deadline=-2.0),
    ]
    subject, _, _ = build_digest_email(items, NOW)
    assert subject == "CubeSmart turnaround: 1 overdue, 2 due soon"


def test_html_contains_rows_links_and_sections() -> None:
    items = [
        _item(extended_status="WAITING FOR QUOTE"),
        _item(
            sc_number="345610548",
            extended_status="WAITING FOR APPROVAL",
            section="waiting_on_cubesmart",
        ),
    ]
    _, html, text = build_digest_email(items, NOW)

    assert "WO #353085818" in html
    assert "WO #345610548" in html
    assert "Needs your action (1)" in html
    assert "Waiting on CubeSmart (1)" in html
    assert "Waiting For Quote" in html
    assert "Overdue 12d" in html
    assert "https://app.brenkfacilityservices.com/work-orders/42" in html
    assert "https://www.servicechannel.com/sc/wo/Workorders/index?id=99" in html

    # Plain-text mirrors the essentials.
    assert "WO #353085818" in text
    assert "Needs your action (1):" in text
    assert "Waiting on CubeSmart (1):" in text
    assert "https://app.brenkfacilityservices.com/work-orders/42" in text


def test_empty_section_is_omitted() -> None:
    _, html, text = build_digest_email([_item()], NOW)
    assert "Waiting on CubeSmart" not in html
    assert "Waiting on CubeSmart" not in text


def test_row_cap_with_overflow_link() -> None:
    items = [
        _item(sc_number=str(n), days_past_deadline=float(n))
        for n in range(MAX_ROWS_PER_SECTION + 5)
    ]
    _, html, text = build_digest_email(items, NOW)
    assert "+5 more" in html
    assert "+5 more" in text
    assert "deadline=at_risk" in html


def test_location_and_status_are_escaped() -> None:
    items = [_item(location="<script>alert(1)</script>")]
    _, html, _ = build_digest_email(items, NOW)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
