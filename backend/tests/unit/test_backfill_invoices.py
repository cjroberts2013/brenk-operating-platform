"""Unit tests for the invoice backfill parser (pure, no DB / no files)."""

from datetime import UTC, datetime
from decimal import Decimal

from scripts.backfill_invoices import (
    build_header_map,
    norm_date,
    norm_decimal,
    norm_int,
    norm_status,
    normalize_row,
)


# --------------------------------------------------------------------------- #
# Header mapping
# --------------------------------------------------------------------------- #
def test_header_map_matches_varied_casing_and_punctuation() -> None:
    headers = [
        "Invoice #",
        "WO Tracking Number",
        "Status",
        "Invoice Total",
        "Paid Date",
        "Some Unknown Column",
    ]
    mapping, unmapped = build_header_map(headers)
    assert mapping["invoice_number"] == "Invoice #"
    assert mapping["wo_tracking_number"] == "WO Tracking Number"
    assert mapping["status"] == "Status"
    assert mapping["invoice_total"] == "Invoice Total"
    assert mapping["paid_date"] == "Paid Date"
    assert unmapped == ["Some Unknown Column"]


def test_header_map_reports_missing_required() -> None:
    mapping, _ = build_header_map(["Status", "Total"])
    assert "invoice_number" not in mapping


# --------------------------------------------------------------------------- #
# Value normalization
# --------------------------------------------------------------------------- #
def test_norm_decimal_handles_currency_formatting() -> None:
    assert norm_decimal("$1,234.56") == Decimal("1234.56")
    assert norm_decimal("  78.00 ") == Decimal("78.00")
    assert norm_decimal("(50.00)") == Decimal("-50.00")  # parens = negative
    assert norm_decimal("") is None
    assert norm_decimal(None) is None


def test_norm_int_strips_non_digits() -> None:
    assert norm_int("351,837,524") == 351837524
    assert norm_int("WO-12345") == 12345
    assert norm_int("") is None


def test_norm_date_parses_us_and_iso() -> None:
    assert norm_date("06/14/2026") == datetime(2026, 6, 14, tzinfo=UTC)
    assert norm_date("2026-06-14") == datetime(2026, 6, 14, tzinfo=UTC)
    assert norm_date("06/14/2026 13:30") == datetime(2026, 6, 14, 13, 30, tzinfo=UTC)
    assert norm_date("not a date") is None
    assert norm_date(None) is None


def test_norm_date_passes_through_datetime_from_xlsx() -> None:
    # openpyxl yields real datetimes for date cells; tag them UTC.
    naive = datetime(2026, 6, 14, 9, 0)
    assert norm_date(naive) == datetime(2026, 6, 14, 9, 0, tzinfo=UTC)


def test_norm_status_canonicalizes() -> None:
    assert norm_status("paid") == "Paid"
    assert norm_status("VOIDED") == "Void"
    assert norm_status("On Hold") == "On Hold"
    assert norm_status("in review") == "Reviewed"
    # Unknown statuses pass through untouched rather than being dropped.
    assert norm_status("Weird") == "Weird"
    assert norm_status("") is None


# --------------------------------------------------------------------------- #
# Whole-row normalization
# --------------------------------------------------------------------------- #
def test_normalize_row_end_to_end() -> None:
    headers = [
        "Invoice #",
        "WO Tracking Number",
        "Status",
        "Invoice Total",
        "Invoice Tax",
        "Paid Date",
        "Trade",
    ]
    mapping, _ = build_header_map(headers)
    raw = {
        "Invoice #": "BRENK351837524",
        "WO Tracking Number": "351837524",
        "Status": "paid",
        "Invoice Total": "$216.50",
        "Invoice Tax": "$16.50",
        "Paid Date": "06/01/2026",
        "Trade": " Electrical ",
    }
    row = normalize_row(raw, mapping)
    assert row["invoice_number"] == "BRENK351837524"
    assert row["wo_tracking_number"] == 351837524
    assert row["status"] == "Paid"
    assert row["invoice_total"] == Decimal("216.50")
    assert row["invoice_tax"] == Decimal("16.50")
    assert row["paid_date"] == datetime(2026, 6, 1, tzinfo=UTC)
    assert row["trade"] == "Electrical"
