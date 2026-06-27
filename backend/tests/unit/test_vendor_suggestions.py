"""Unit tests for the vendor-suggestion scoring.

DB-free: builds transient WorkOrder/Vendor/Trade/Location instances and feeds
them straight to the pure service.
"""

from app.models.work_order import JobType, Location, Trade, Vendor, WorkOrder
from app.services.vendor_suggestions import (
    STRONG_MATCH_THRESHOLD,
    build_vendor_suggestions,
    match_service_area,
    trade_name_matches,
)


def _jt(jid: int, name: str) -> JobType:
    # is_active/is_catchall are DB-side defaults — set them on transient rows.
    jt = JobType(name=name, description=None, is_active=True, is_catchall=False)
    jt.id = jid
    jt.position = jid
    return jt


def _trade(tid: int, name: str) -> Trade:
    t = Trade(name=name)
    t.id = tid
    return t


def _vendor(vid: int, name: str, *, skills=(), service_area=None) -> Vendor:
    # is_active is a DB-side default (applied at flush), so set it explicitly
    # on these transient instances — a real row loaded from the DB always has it.
    v = Vendor(name=name, service_area=service_area, is_active=True)
    v.id = vid
    v.job_types = list(skills)
    return v


def _wo(*, category=None, trade=None, city=None, region=None, assigned_vendor_id=None) -> WorkOrder:
    wo = WorkOrder(sc_work_order_id=1, sc_number="WO-1", primary_status="IN PROGRESS")
    wo.brenk_category = category
    wo.trade = trade
    wo.trade_id = trade.id if trade is not None else None
    if city is not None or region is not None:
        loc = Location()
        loc.raw_data = {"City": city} if city else None
        loc.region = region
        wo.location = loc
    else:
        wo.location = None
    wo.assigned_vendor_id = assigned_vendor_id
    return wo


# --- match_service_area --------------------------------------------------


def test_service_area_wildcard_anywhere() -> None:
    assert match_service_area("Anywhere", "Austin", None) == (0.7, "travels anywhere")


def test_service_area_wildcard_blank() -> None:
    assert match_service_area(None, "Austin", None) == (0.7, "travels anywhere")
    assert match_service_area("  ", "Austin", None) == (0.7, "travels anywhere")


def test_service_area_region_expansion() -> None:
    # Cedar Park belongs to the Austin region; a vendor covering "Austin metro"
    # should cover a Cedar Park job.
    score, reason = match_service_area("Austin & San Antonio", "Cedar Park", None)
    assert score == 1.0
    assert reason == "covers Cedar Park"


def test_service_area_direct_city_match() -> None:
    assert match_service_area("Austin", "Austin", None) == (1.0, "covers Austin")


def test_service_area_outside() -> None:
    assert match_service_area("Longview only", "Austin", None) == (0.0, "outside Austin")


def test_service_area_unknown_location() -> None:
    assert match_service_area("Austin", None, None) == (0.5, "location unknown")


# --- trade_name_matches (cross-vocabulary) ------------------------------


def test_trade_name_matches_across_vocabularies() -> None:
    # SC catalog (WO) ↔ Brenk (vendor) names — different rows, same meaning.
    assert trade_name_matches("ELECTRICAL", ["Electrical"])
    assert trade_name_matches("DOORS", ["Commercial Door Repair"])
    assert trade_name_matches("DOORS ROLL UP", ["Roll-Up Door Repair"])
    assert trade_name_matches("PLUMBING", ["Plumber"])
    assert trade_name_matches("FENCING", ["Wood Fence Repair"])
    assert trade_name_matches("GATE/KEY PADS", ["Gate Repair"])


def test_trade_name_no_false_match() -> None:
    assert not trade_name_matches("ROOFING", ["Electrical", "Plumber"])
    assert not trade_name_matches("BULK TRASH REMOVAL", ["Flooring"])
    # All-noise WO trade name → no basis to match.
    assert not trade_name_matches("GENERAL BUILDING", ["Handyman"])


# --- build_vendor_suggestions -------------------------------------------


def test_category_gate_excludes_non_matching() -> None:
    # WO categorized "Electrical" — only vendors with that skill are eligible.
    elec = _jt(5, "Electrical")
    plumb = _jt(9, "Plumbing")
    wo = _wo(category="Electrical", city="Austin")
    electrician = _vendor(1, "Sparky", skills=[elec], service_area="Austin")
    plumber = _vendor(2, "Drip", skills=[plumb], service_area="Austin")

    resp = build_vendor_suggestions(wo, [electrician, plumber], {})

    assert [s.vendor.id for s in resp.ranked] == [1]
    assert resp.has_trade is True
    assert resp.wo_city == "Austin"


def test_no_vendor_with_skill_yields_empty() -> None:
    wo = _wo(category="Roofing", city="Austin")
    v = _vendor(1, "Sparky", skills=[_jt(5, "Electrical")], service_area="Austin")

    resp = build_vendor_suggestions(wo, [v], {})

    assert resp.has_trade is True
    assert resp.ranked == []
    assert resp.top_pick is None


def test_uncategorized_wo_falls_back_to_sc_trade() -> None:
    # No brenk_category yet → fuzzy-match the SC trade name vs the skill name.
    wo = _wo(trade=_trade(3, "ELECTRICAL"), city="Austin")
    v = _vendor(1, "Sparky", skills=[_jt(5, "Electrical")], service_area="Austin")

    resp = build_vendor_suggestions(wo, [v], {1: 0})

    assert resp.top_pick is not None
    assert resp.top_pick.vendor.id == 1
    assert resp.top_pick.reason.startswith("Does ELECTRICAL")


def test_workload_decay_orders_idle_vendor_first() -> None:
    elec = _jt(5, "Electrical")
    wo = _wo(category="Electrical", city="Austin")
    busy = _vendor(1, "Aaa Busy", skills=[elec], service_area="Austin")
    idle = _vendor(2, "Bbb Idle", skills=[elec], service_area="Austin")

    resp = build_vendor_suggestions(wo, [busy, idle], {1: 3, 2: 0})

    assert [s.vendor.id for s in resp.ranked] == [2, 1]
    assert resp.top_pick is not None
    assert resp.top_pick.vendor.id == 2


def test_below_threshold_yields_no_top_pick() -> None:
    elec = _jt(5, "Electrical")
    wo = _wo(category="Electrical", city="Austin")
    far = _vendor(1, "Faraway", skills=[elec], service_area="Longview only")

    resp = build_vendor_suggestions(wo, [far], {})

    assert resp.top_pick is None
    assert len(resp.ranked) == 1
    assert resp.ranked[0].composite_score < STRONG_MATCH_THRESHOLD


def test_assigned_vendor_flagged_and_excluded_from_top_pick() -> None:
    elec = _jt(5, "Electrical")
    current = _vendor(1, "Aaa Current", skills=[elec], service_area="Austin")
    other = _vendor(2, "Bbb Other", skills=[elec], service_area="Austin")
    wo = _wo(category="Electrical", city="Austin", assigned_vendor_id=1)

    resp = build_vendor_suggestions(wo, [current, other], {})

    current_row = next(s for s in resp.ranked if s.vendor.id == 1)
    assert current_row.is_current is True
    assert resp.top_pick is not None
    assert resp.top_pick.vendor.id == 2


def test_no_category_or_trade_opens_gate() -> None:
    wo = _wo(category=None, trade=None, city="Austin")
    v = _vendor(1, "Generalist", skills=[_jt(5, "Electrical")], service_area="Austin")

    resp = build_vendor_suggestions(wo, [v], {})

    assert resp.has_trade is False
    assert len(resp.ranked) == 1
    assert resp.ranked[0].trade.reason == "Job type unknown"


def test_reason_string_format() -> None:
    elec = _jt(5, "Electrical")
    wo = _wo(category="Electrical", city="Austin")
    v = _vendor(1, "Sparky", skills=[elec], service_area="Austin")

    resp = build_vendor_suggestions(wo, [v], {1: 1})

    assert resp.top_pick is not None
    assert resp.top_pick.reason == "Does Electrical · covers Austin · 1 active job"


def test_deterministic() -> None:
    elec = _jt(5, "Electrical")
    wo = _wo(category="Electrical", city="Austin")
    vendors = [
        _vendor(1, "Aaa", skills=[elec], service_area="Austin"),
        _vendor(2, "Bbb", skills=[elec], service_area="Anywhere"),
    ]
    counts = {1: 1, 2: 0}

    first = build_vendor_suggestions(wo, vendors, counts).model_dump()
    second = build_vendor_suggestions(wo, vendors, counts).model_dump()
    assert first == second
