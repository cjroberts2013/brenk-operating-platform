"""Sync-freshness health signal (pure, no DB / no I/O).

Powers `GET /health/sync-freshness`, the external dead-man's-switch: if the
worker's hourly WO sync stops (a silent worker stall), the newest
`work_orders.last_synced_at` goes stale and this reports unhealthy so an
external monitor can alert a human. Kept pure so it's trivially testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class SyncFreshness:
    fresh: bool
    last_synced_at: datetime | None
    age_seconds: int | None
    threshold_seconds: int
    reason: str | None = None

    def to_dict(self) -> dict:
        return {
            "fresh": self.fresh,
            "last_synced_at": self.last_synced_at.isoformat() if self.last_synced_at else None,
            "age_seconds": self.age_seconds,
            "threshold_seconds": self.threshold_seconds,
            "reason": self.reason,
        }


def evaluate_sync_freshness(
    last_synced_at: datetime | None,
    now: datetime,
    max_age_seconds: int,
) -> SyncFreshness:
    """Classify sync freshness from the newest last_synced_at.

    Stale (or no data at all) → fresh=False, which the endpoint maps to a
    503 so an external check fails and alerts.
    """
    if last_synced_at is None:
        return SyncFreshness(
            fresh=False,
            last_synced_at=None,
            age_seconds=None,
            threshold_seconds=max_age_seconds,
            reason="no work orders have ever synced",
        )
    age = max(0, int((now - last_synced_at).total_seconds()))
    fresh = age <= max_age_seconds
    return SyncFreshness(
        fresh=fresh,
        last_synced_at=last_synced_at,
        age_seconds=age,
        threshold_seconds=max_age_seconds,
        reason=None if fresh else f"last sync was {age}s ago (> {max_age_seconds}s)",
    )
