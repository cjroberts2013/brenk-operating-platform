"""Address formatting from ServiceChannel `raw_data` blobs.

SC location payloads carry Address1/City/State/Zip; we surface a one-line
address for display without normalizing them into columns. Shared by the
locations API and the vendor-message composer.
"""

from typing import Any


def format_address(raw: dict[str, Any] | None) -> str | None:
    """Build a one-line address from an SC location raw_data blob, or None."""
    if not raw:
        return None
    street = (raw.get("Address1") or "").strip()
    city = (raw.get("City") or "").strip()
    state = (raw.get("State") or "").strip()
    zip_code = (raw.get("Zip") or "").strip()
    city_line = ", ".join(p for p in [city, state] if p)
    if zip_code:
        city_line = f"{city_line} {zip_code}".strip()
    full = ", ".join(p for p in [street, city_line] if p)
    return full or None
