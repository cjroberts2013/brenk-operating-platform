"""Self-heal watchdog for the Procrastinate worker.

The worker died silently for 18 days once: its Postgres LISTEN/NOTIFY
connection dropped, the periodic scheduler wedged, but the process stayed
"up" — so Fly never restarted it and every hourly task (WO sync,
categorization, deadline digest, webhook sweep) quietly stopped.

The fix: a per-minute heartbeat plus an independent watchdog thread. The
`worker_heartbeat` periodic task touches a file every minute; if the
scheduler wedges, the file stops updating. The watchdog runs in its own OS
thread (not the asyncio loop, so it keeps ticking even if the loop wedges)
and force-exits the process when the heartbeat goes stale — letting Fly's
restart-on-exit bring the worker back.

Enabled only on the worker (settings.WORKER_WATCHDOG, set via
fly.worker.toml) so imports elsewhere (web, tests) never spawn the thread.
"""

from __future__ import annotations

import os
import threading
import time

import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

# How often the watchdog thread checks the heartbeat.
_CHECK_INTERVAL_SECONDS = 60

_started = False
_start_lock = threading.Lock()


def write_heartbeat(path: str | None = None) -> None:
    """Record 'the scheduler is alive right now' — called every minute by
    the worker_heartbeat task. Best-effort; a write failure is logged, not
    raised (it must never fail the task)."""
    path = path or get_settings().WORKER_HEARTBEAT_FILE
    try:
        with open(path, "w") as fh:
            fh.write(str(time.time()))
    except OSError as exc:
        logger.warning("worker_heartbeat_write_failed", path=path, error=str(exc))


def heartbeat_age_seconds(path: str, now: float | None = None) -> float | None:
    """Seconds since the heartbeat was last written, or None if it doesn't
    exist yet (never written)."""
    now = time.time() if now is None else now
    try:
        with open(path) as fh:
            beat = float(fh.read().strip())
    except (OSError, ValueError):
        return None
    return max(0.0, now - beat)


def _watchdog_loop() -> None:
    settings = get_settings()
    path = settings.WORKER_HEARTBEAT_FILE
    stall = settings.WORKER_STALL_SECONDS
    started_at = time.time()

    logger.info("worker_watchdog_started", heartbeat_file=path, stall_seconds=stall)
    while True:
        time.sleep(_CHECK_INTERVAL_SECONDS)
        # Startup grace: give the worker time to boot and write its first
        # heartbeat before we're willing to judge it stale.
        if time.time() - started_at < stall:
            continue
        age = heartbeat_age_seconds(path)
        if age is None:
            # Past the grace window with no heartbeat ever written — the
            # scheduler never came up. Restart to try again.
            logger.critical("worker_watchdog_no_heartbeat", heartbeat_file=path)
            os._exit(1)
        if age > stall:
            logger.critical(
                "worker_watchdog_stale_heartbeat_restarting",
                age_seconds=round(age),
                stall_seconds=stall,
            )
            os._exit(1)


def start_watchdog() -> None:
    """Start the watchdog thread once (idempotent). No-op unless
    settings.WORKER_WATCHDOG is set — so only the worker process runs it."""
    global _started
    if not get_settings().WORKER_WATCHDOG:
        return
    with _start_lock:
        if _started:
            return
        _started = True
        threading.Thread(target=_watchdog_loop, name="worker-watchdog", daemon=True).start()
