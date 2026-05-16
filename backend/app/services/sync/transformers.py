"""Pure transformers from ServiceChannel payloads to ORM column dicts.

These functions do no I/O. They take a raw SC API response dict and return
a dict of values suitable for constructing or updating one of our ORM
models. Foreign-key resolution is the caller's responsibility — the
transformers only emit the natural keys (sc_subscriber_id, sc_location_id,
sc_trade_id) so the upserter can look up the real FK ids.

Why split this out: trivial to unit-test against captured fixtures, and
the orchestration code stays readable.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any


def parse_utc(value: str | None) -> datetime | None:
    """Parse an SC UTC timestamp string into a timezone-aware datetime.

    SC returns UTC timestamps as ISO 8601 strings, often with a trailing 'Z'
    (e.g. "2026-05-08T22:44:31.3040379Z"). Python's fromisoformat handles 'Z'
    in 3.11+, but we accept None and pass-through to make caller code tidy.
    """
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _to_decimal(value: Any) -> Decimal | None:
    """Coerce a JSON number to Decimal without losing precision."""
    if value is None:
        return None
    return Decimal(str(value))


def extract_client_fields(subscriber: dict[str, Any]) -> dict[str, Any]:
    """Extract Client column values from a payload's Subscriber sub-object."""
    return {
        "sc_subscriber_id": subscriber["Id"],
        "name": subscriber["Name"],
        "short_name": subscriber.get("ShortName"),
        "is_outsourced": bool(subscriber.get("IsOutsourcedWorkOn", False)),
        "raw_data": subscriber,
    }


def extract_location_fields(location: dict[str, Any]) -> dict[str, Any]:
    """Extract Location column values from a payload's Location sub-object.

    Note: the top-level `LocationId` field on a work order is unreliable
    (often 0 — see docs/architecture/servicechannel-api.md). Always use the
    nested `Location.Id`, which is what this function reads.
    """
    return {
        "sc_location_id": location["Id"],
        "store_id": location.get("StoreId"),
        "name": location.get("Name") or location.get("ShortName"),
        "latitude": _to_decimal(location.get("Latitude")),
        "longitude": _to_decimal(location.get("Longitude")),
        "region": location.get("Region"),
        "district": location.get("District"),
        "timezone_offset": location.get("TimeShiftToEST"),
        "is_international": bool(location.get("IsInternational", False)),
        "raw_data": location,
    }


def extract_trade_fields(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Extract Trade column values from a work order payload.

    Trade is denormalized on the work order: a string name (`Trade`) and a
    numeric SC id (`TradeId`). Returns None if neither is present.
    """
    name = payload.get("Trade")
    sc_trade_id = payload.get("TradeId")
    if not name and not sc_trade_id:
        return None
    return {"name": name, "sc_trade_id": sc_trade_id}


def extract_work_order_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract WorkOrder column values from a top-level SC payload.

    FK ids (client_id, location_id, trade_id, assigned_vendor_id) are NOT
    populated here — the upserter resolves those after creating/finding the
    related rows.
    """
    status = payload.get("Status") or {}
    currency = payload.get("Currency") or {}
    notes_summary = (payload.get("Notes") or {}).get("Count") or {}
    attachments_summary = (payload.get("Attachments") or {}).get("Count") or {}

    return {
        "sc_work_order_id": payload["Id"],
        "sc_number": payload["Number"],
        "sc_purchase_number": payload.get("PurchaseNumber"),
        "primary_status": status["Primary"],
        "extended_status": status.get("Extended"),
        "can_create_invoice": bool(status.get("CanCreateInvoice", False)),
        "category": payload.get("Category"),
        "sc_category_id": payload.get("CategoryId"),
        "priority": payload.get("Priority"),
        "problem_code": payload.get("ProblemCode"),
        "description": payload.get("Description"),
        "resolution": payload.get("Resolution"),
        "caller": payload.get("Caller"),
        "approval_code": payload.get("ApprovalCode"),
        "nte": _to_decimal(payload.get("Nte")),
        "currency_code": currency.get("AlphabeticalCode") or "USD",
        "call_date": parse_utc(payload.get("CallDate")),
        "scheduled_date": parse_utc(payload.get("ScheduledDate")),
        "expiration_date": parse_utc(payload.get("ExpirationDate")),
        "original_eta": parse_utc(payload.get("OriginalETA")),
        "sc_updated_date": parse_utc(payload.get("UpdatedDate")),
        "completed_date": parse_utc(payload.get("CompletedDate")),
        "is_invoiced": bool(payload.get("IsInvoiced", False)),
        "is_expired": bool(payload.get("IsExpired", False)),
        "is_check_in_denied": bool(payload.get("IsCheckInDenied", False)),
        "has_work_activity": bool(payload.get("HasWorkActivity", False)),
        "auto_complete": bool(payload.get("AutoComplete", False)),
        "auto_invoice": bool(payload.get("AutoInvoice", False)),
        "notes_count": notes_summary.get("Total", 0),
        "attachments_count": attachments_summary.get("Total", 0),
        "raw_data": payload,
    }


def extract_note_fields(note: dict[str, Any]) -> dict[str, Any]:
    """Extract WorkOrderNote column values from a single note dict.

    The note can come from either the inline `Notes.Last` summary on a list
    response or a full record from the /notes endpoint. Both shapes share
    the same field names.
    """
    return {
        "sc_note_id": note.get("Id"),
        "sc_document_id": note.get("DocumentId"),
        "note_number": note.get("Number"),
        "note_data": note.get("NoteData", ""),
        "note_type": note.get("NoteType"),
        "visibility": note.get("Visibility"),
        "action_required": bool(note.get("ActionRequired", False)),
        "is_pinned": bool(note.get("IsPinned", False)),
        "is_attachment_note": bool(note.get("IsAttachmentNote", False)),
        "created_by": note.get("CreatedBy"),
        "company_name": note.get("CompanyName"),
        "created_at_sc": parse_utc(note.get("DateCreated")),
        "source": "servicechannel",
        "raw_data": note,
    }
