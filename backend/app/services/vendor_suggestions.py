"""Vendor suggestion scoring — pure, DB-free, deterministic.

`build_vendor_suggestions` takes a work order (with `trade` + `location`
loaded), a list of active vendors (with `job_types` loaded), and the
precomputed open-WO counts, and returns the ranked `VendorSuggestionResponse`
the assign-step UI consumes.

Three axes:
  - Skill is a GATE. Vendor skills and the WO's AI category are the same shared
    `job_types` vocabulary, so the primary match is exact (WO's `brenk_category`
    == a vendor skill). When the WO isn't categorized yet, we fall back to
    fuzzy-matching the SC trade name against the vendor's skill names.
  - Location scores the vendor's free-text `service_area` against the WO's city
    via a small curated region table (no geocoding, no LLM — Brenk's footprint
    is the Austin + San Antonio corridor).
  - Workload rewards vendors carrying fewer open jobs.

Deterministic on purpose: the same inputs always rank the same way, so Daryl
can trust (and reproduce) the recommendation. Mirrors the pure-service shape of
`reports.py` / `money.py`.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from app.models.work_order import Vendor, WorkOrder
from app.schemas.vendor import (
    VendorSuggestion,
    VendorSuggestionAxis,
    VendorSuggestionResponse,
    VendorSummary,
)

# Axis weights (trade is already gated, so it doesn't carry weight here).
# Location dominates — a vendor outside the area is a non-starter — and
# workload breaks ties among in-area vendors.
W_LOC = 0.65
W_LOAD = 0.35

# A top candidate must clear this composite to be offered as a one-click pick;
# below it the UI falls back to the manual dropdown.
STRONG_MATCH_THRESHOLD = 0.5

# Region keyword expansion. A WO whose city is any of the listed towns is
# considered "covered" by a vendor whose free-text service_area names the
# region or any town in it (Brenk's vendors mostly say "Austin & San
# Antonio"). Covers the actual Austin + San Antonio corridor Brenk's stores
# sit in — add a town here as new areas show up.
_REGION_KEYWORDS: dict[str, list[str]] = {
    "austin": [
        "austin",
        "round rock",
        "cedar park",
        "pflugerville",
        "georgetown",
        "leander",
        "kyle",
        "buda",
        "del valle",
        "lakeway",
        "manor",
        "san marcos",
        "dripping springs",
        "bee cave",
        "hutto",
        "elgin",
        "bastrop",
        "metro",
    ],
    "san antonio": [
        "san antonio",
        "schertz",
        "new braunfels",
        "boerne",
        "converse",
        "seguin",
        "canyon lake",
        "cibolo",
        "universal city",
        "helotes",
        "live oak",
        "selma",
    ],
}

# Noise words stripped before matching a WO's trade name (SC catalog, e.g.
# "GENERAL BUILDING", "EXTERIOR BUILDING REPAIRS") against a vendor's trade
# names (Brenk, e.g. "Commercial Door Repair"). The two are different rows in
# different id spaces, so we match on normalized name stems, not id.
_TRADE_STOPWORDS = frozenset(
    {
        "repair",
        "repairs",
        "commercial",
        "building",
        "general",
        "service",
        "services",
        "system",
        "systems",
    }
)


def _trade_words(name: str | None) -> list[str]:
    """Significant lowercased words (≥4 chars, non-noise) from a trade name."""
    if not name:
        return []
    return [
        w for w in re.split(r"[^a-z]+", name.lower()) if len(w) >= 4 and w not in _TRADE_STOPWORDS
    ]


def trade_name_matches(wo_trade_name: str | None, vendor_trade_names: Iterable[str]) -> bool:
    """True if the WO's trade and any of the vendor's trades share a word stem.

    Matches across the SC↔Brenk vocab gap by comparing 4-char prefixes —
    "ELECTRICAL"/"Electrical", "DOORS"/"Commercial Door Repair",
    "PLUMBING"/"Plumber", "FENCING"/"Wood Fence Repair" all match; "ROOFING"
    with no roofer tagged does not.
    """
    wo_words = _trade_words(wo_trade_name)
    if not wo_words:
        return False
    wo_stems = {w[:4] for w in wo_words}
    for vt in vendor_trade_names:
        for vw in _trade_words(vt):
            if vw[:4] in wo_stems:
                return True
    return False


def match_service_area(
    service_area: str | None,
    wo_city: str | None,
    wo_region: str | None,
) -> tuple[float, str]:
    """Score (0..1) how well a vendor's free-text service area covers the WO's
    city/region, with a human reason. Wildcard for blank/"anywhere"."""
    sa = (service_area or "").strip().lower()
    if not sa or sa == "any" or "anywhere" in sa:
        return 0.7, "travels anywhere"

    city = (wo_city or "").strip()
    region = (wo_region or "").strip()
    if not city and not region:
        return 0.5, "location unknown"

    # Tokens that count as "covers this job": the city/region itself, plus —
    # if it belongs to a known region group — every keyword in that group.
    tokens: set[str] = set()
    for value in (city, region):
        v = value.strip().lower()
        if not v:
            continue
        tokens.add(v)
        for grp, towns in _REGION_KEYWORDS.items():
            if v == grp or v in towns:
                tokens.add(grp)
                tokens.update(towns)

    label = city or region
    if any(tok and tok in sa for tok in tokens):
        return 1.0, f"covers {label}"
    return 0.0, f"outside {label}"


def _workload_score(active_count: int) -> float:
    """Fewer open jobs → higher score. 0→1.0, 1→0.5, 2→0.33, 3→0.25."""
    return 1.0 / (1 + max(0, active_count))


def _workload_reason(active_count: int) -> str:
    if active_count <= 0:
        return "no active jobs"
    return f"{active_count} active job{'s' if active_count != 1 else ''}"


def score_vendor(
    vendor: Vendor,
    wo: WorkOrder,
    *,
    wo_city: str | None,
    wo_region: str | None,
    wo_category: str | None,
    trade_name: str | None,
    active_count: int,
    is_current: bool,
) -> VendorSuggestion | None:
    """Score one vendor for one WO. Returns None when the skill gate excludes
    the vendor (they don't do the WO's job type)."""
    skills = [jt.name for jt in vendor.job_types]

    if wo_category:
        # Primary: exact match on the shared taxonomy (categorized WO).
        if wo_category.lower() not in {s.lower() for s in skills}:
            return None
        skill_score = 1.0
        skill_reason = f"Does {wo_category}"
    elif trade_name:
        # Fallback: WO not categorized yet — fuzzy-match the SC trade name.
        if not trade_name_matches(trade_name, skills):
            return None
        skill_score = 1.0
        skill_reason = f"Does {trade_name}"
    else:
        # No category and no trade — gate opens, skill can't rank.
        skill_score = 0.5
        skill_reason = "Job type unknown"

    loc_score, loc_reason = match_service_area(vendor.service_area, wo_city, wo_region)
    load_score = _workload_score(active_count)
    load_reason = _workload_reason(active_count)

    composite = W_LOC * loc_score + W_LOAD * load_score
    reason = " · ".join([skill_reason, loc_reason, load_reason])

    return VendorSuggestion(
        vendor=VendorSummary.from_vendor(vendor, active_count),
        composite_score=round(composite, 4),
        trade=VendorSuggestionAxis(score=skill_score, reason=skill_reason),
        location=VendorSuggestionAxis(score=loc_score, reason=loc_reason),
        workload=VendorSuggestionAxis(score=round(load_score, 4), reason=load_reason),
        reason=reason,
        is_current=is_current,
    )


def build_vendor_suggestions(
    wo: WorkOrder,
    vendors: Iterable[Vendor],
    active_counts: dict[int, int],
) -> VendorSuggestionResponse:
    """Rank skill-eligible vendors for a work order's assign step."""
    raw = wo.location.raw_data if wo.location else None
    wo_city = (raw or {}).get("City") if raw else None
    wo_region = wo.location.region if wo.location else None
    wo_category = wo.brenk_category
    trade_name = wo.trade.name if wo.trade else None
    assigned_id = wo.assigned_vendor_id

    scored: list[VendorSuggestion] = []
    for vendor in vendors:
        suggestion = score_vendor(
            vendor,
            wo,
            wo_city=wo_city,
            wo_region=wo_region,
            wo_category=wo_category,
            trade_name=trade_name,
            active_count=active_counts.get(vendor.id, 0),
            is_current=(vendor.id == assigned_id),
        )
        if suggestion is not None:
            scored.append(suggestion)

    # Deterministic order: best composite first, then fewer active jobs, then
    # alphabetical — matches the Vendor.name/id ordering used elsewhere.
    scored.sort(
        key=lambda s: (
            -s.composite_score,
            s.vendor.active_work_orders,
            s.vendor.name.lower(),
            s.vendor.id,
        )
    )

    # Top pick = best non-current candidate, only if it clears the threshold.
    top_pick: VendorSuggestion | None = None
    for suggestion in scored:
        if suggestion.is_current:
            continue
        if suggestion.composite_score >= STRONG_MATCH_THRESHOLD:
            top_pick = suggestion
        break

    return VendorSuggestionResponse(
        top_pick=top_pick,
        ranked=scored,
        # True when there's a basis to gate on (a category or an SC trade).
        has_trade=bool(wo_category or trade_name),
        wo_city=wo_city,
    )
