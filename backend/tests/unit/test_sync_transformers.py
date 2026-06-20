"""Tests for the pure SC-payload-to-ORM-field transformers."""

from datetime import UTC, datetime
from decimal import Decimal

from app.services.sync.transformers import (
    extract_client_fields,
    extract_location_fields,
    extract_note_fields,
    extract_trade_fields,
    extract_work_order_fields,
    parse_utc,
)


def test_parse_utc_handles_z_suffix() -> None:
    result = parse_utc("2026-05-08T22:44:31.3040379Z")
    assert result == datetime(2026, 5, 8, 22, 44, 31, 304037, tzinfo=UTC)
    assert result is not None
    assert result.tzinfo is UTC


def test_parse_utc_handles_none() -> None:
    assert parse_utc(None) is None
    assert parse_utc("") is None


def test_extract_client_fields(sample_work_order_list: list[dict]) -> None:
    payload = sample_work_order_list[0]
    fields = extract_client_fields(payload["Subscriber"])
    assert fields["sc_subscriber_id"] == 9990001
    assert fields["name"] == "ACME CORP"
    assert fields["short_name"] == "ACME"
    assert fields["is_outsourced"] is False
    assert fields["raw_data"] == payload["Subscriber"]


def test_extract_location_uses_nested_id(sample_work_order_list: list[dict]) -> None:
    """The top-level LocationId is 0; we must read Location.Id instead."""
    payload = sample_work_order_list[0]
    assert payload["LocationId"] == 0  # confirm the quirk is present in fixture
    fields = extract_location_fields(payload["Location"])
    assert fields["sc_location_id"] == 9990002
    assert fields["store_id"] == "0001"
    assert fields["latitude"] == Decimal("30.5")
    assert fields["longitude"] == Decimal("-97.5")
    assert fields["is_international"] is False


def test_extract_location_fields_are_sc_only(sample_work_order_list: list[dict]) -> None:
    """The transformer must never emit Brenk enrichment keys — upsert_location
    writes from this dict, and the sync must not clobber operator-entered
    district-manager / rating / description data. Guards the allowlist."""
    fields = extract_location_fields(sample_work_order_list[0]["Location"])
    brenk_only = {
        "district_manager_name",
        "district_manager_phone",
        "district_manager_email",
        "rating",
        "description",
    }
    assert brenk_only.isdisjoint(fields.keys())


def test_extract_trade_prefers_id(sample_work_order_list: list[dict]) -> None:
    fields = extract_trade_fields(sample_work_order_list[0])
    assert fields is not None
    assert fields["sc_trade_id"] == 5001
    assert fields["name"] == "ROOFING"


def test_extract_trade_returns_none_when_absent() -> None:
    assert extract_trade_fields({}) is None


def test_extract_work_order_top_level_fields(sample_work_order_list: list[dict]) -> None:
    payload = sample_work_order_list[0]
    fields = extract_work_order_fields(payload)

    assert fields["sc_work_order_id"] == 1000000001
    assert fields["sc_number"] == "1000000001"
    assert fields["primary_status"] == "IN PROGRESS"
    assert fields["extended_status"] == "DISPATCH CONFIRMED"
    assert fields["can_create_invoice"] is False
    assert fields["category"] == "REPAIR"
    assert fields["sc_category_id"] == 10192
    assert fields["priority"] == "Same day - Biz Hrs"
    assert fields["problem_code"] == "OTHER ISSUES"
    assert fields["nte"] == Decimal("750.0")
    assert fields["currency_code"] == "USD"
    assert fields["is_expired"] is True
    assert fields["is_invoiced"] is False
    assert fields["notes_count"] == 6
    assert fields["attachments_count"] == 2


def test_extract_work_order_timestamps_are_utc(sample_work_order_list: list[dict]) -> None:
    fields = extract_work_order_fields(sample_work_order_list[0])
    assert fields["call_date"] == datetime(2026, 5, 8, 21, 39, 50, tzinfo=UTC)
    assert fields["scheduled_date"] == datetime(2026, 5, 9, 5, 47, 58, 427000, tzinfo=UTC)
    assert fields["sc_updated_date"] is not None
    assert fields["sc_updated_date"].tzinfo is UTC
    assert fields["completed_date"] is None  # not in the fixture (status not complete)


def test_extract_work_order_raw_data_preserves_full_payload(
    sample_work_order_list: list[dict],
) -> None:
    payload = sample_work_order_list[0]
    fields = extract_work_order_fields(payload)
    assert fields["raw_data"] is payload


def test_extract_work_order_missing_optional_fields() -> None:
    """A minimal payload should not crash; optional fields come back as None/defaults."""
    minimal = {
        "Id": 1,
        "Number": "1",
        "Status": {"Primary": "OPEN"},
    }
    fields = extract_work_order_fields(minimal)
    assert fields["sc_work_order_id"] == 1
    assert fields["primary_status"] == "OPEN"
    assert fields["extended_status"] is None
    assert fields["nte"] is None
    assert fields["currency_code"] == "USD"  # default
    assert fields["notes_count"] == 0
    assert fields["attachments_count"] == 0


def test_extract_note_fields(sample_work_order_list: list[dict]) -> None:
    note = sample_work_order_list[0]["Notes"]["Last"]
    fields = extract_note_fields(note)
    assert fields["sc_note_id"] == 9990004
    assert fields["sc_document_id"] == "00000000-0000-0000-0000-000000000001"
    assert fields["note_number"] == 6
    assert "Status has been changed" in fields["note_data"]
    assert fields["created_by"] == "Test User"
    assert fields["action_required"] is False
    assert fields["created_at_sc"] is not None
    assert fields["created_at_sc"].tzinfo is UTC
    assert fields["source"] == "servicechannel"
