"""Unit tests for sync-freshness evaluation + the watchdog heartbeat file."""

from datetime import UTC, datetime, timedelta

from app.services.health import evaluate_sync_freshness
from app.workers import watchdog

NOW = datetime(2026, 8, 9, 12, 0, 0, tzinfo=UTC)
MAX_AGE = 10800  # 3h


def test_fresh_when_recent() -> None:
    r = evaluate_sync_freshness(NOW - timedelta(minutes=30), NOW, MAX_AGE)
    assert r.fresh is True
    assert r.age_seconds == 1800
    assert r.reason is None
    assert r.to_dict()["fresh"] is True


def test_stale_when_past_threshold() -> None:
    r = evaluate_sync_freshness(NOW - timedelta(hours=5), NOW, MAX_AGE)
    assert r.fresh is False
    assert r.age_seconds == 5 * 3600
    assert "ago" in r.reason


def test_exactly_at_threshold_is_fresh() -> None:
    r = evaluate_sync_freshness(NOW - timedelta(seconds=MAX_AGE), NOW, MAX_AGE)
    assert r.fresh is True


def test_none_is_unhealthy() -> None:
    r = evaluate_sync_freshness(None, NOW, MAX_AGE)
    assert r.fresh is False
    assert r.age_seconds is None
    assert r.last_synced_at is None
    assert "synced" in r.reason


def test_future_timestamp_clamps_to_zero_age() -> None:
    # Clock skew shouldn't produce a negative age.
    r = evaluate_sync_freshness(NOW + timedelta(minutes=5), NOW, MAX_AGE)
    assert r.age_seconds == 0
    assert r.fresh is True


# --------------------------------------------------------------------------- #
# Watchdog heartbeat file
# --------------------------------------------------------------------------- #


def test_heartbeat_roundtrip(tmp_path) -> None:
    path = str(tmp_path / "hb")
    watchdog.write_heartbeat(path)
    age = watchdog.heartbeat_age_seconds(path)
    assert age is not None
    assert age < 5  # just written


def test_heartbeat_age_none_when_missing(tmp_path) -> None:
    assert watchdog.heartbeat_age_seconds(str(tmp_path / "nope")) is None


def test_heartbeat_age_reflects_staleness(tmp_path) -> None:
    import time

    path = str(tmp_path / "hb")
    watchdog.write_heartbeat(path)
    beat = time.time()
    # Evaluate "now" 700s later — should read as ~700s stale.
    age = watchdog.heartbeat_age_seconds(path, now=beat + 700)
    assert 695 <= age <= 705


def test_heartbeat_age_none_on_garbage(tmp_path) -> None:
    path = tmp_path / "hb"
    path.write_text("not-a-float")
    assert watchdog.heartbeat_age_seconds(str(path)) is None
