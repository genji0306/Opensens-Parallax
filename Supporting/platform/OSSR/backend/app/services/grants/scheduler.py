"""
Background scheduler for periodic grant discovery (Phase D.1).

Spawned as a daemon thread at app start (see ``main.py``). Every 5 minutes
it inspects all enabled grant sources, checks their ``schedule`` metadata
string, and runs a crawl for any source that is due.

Schedule format (stored in ``source.metadata['schedule']``):

    daily_HH:MM_utc        e.g. daily_02:00_utc
    weekly_<weekday>       e.g. weekly_monday
    hourly                 (for testing)

We cap concurrent crawls at 3 and log each run to the ``grant_crawl_runs``
table. Per-source error tracking: if a source fails two runs in a row the
scheduler fires a ``source_failure`` alert and backs off until an operator
manually triggers it.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .alerts import fire_source_failure
from .discovery import discover_source
from .models import GrantSource
from .store import (
    list_crawl_runs,
    list_sources,
    save_crawl_run,
)

logger = logging.getLogger(__name__)


_WEEKDAY_MAP = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


class GrantScheduler:
    """
    Lightweight scheduler. Not a generic cron — specific to grant sources.
    Safe to start/stop multiple times; ``start`` is a no-op if already
    running.
    """

    def __init__(
        self,
        tick_seconds: int = 300,
        max_concurrent: int = 3,
        model: str = "",
    ) -> None:
        self.tick_seconds = max(30, int(tick_seconds))
        self.max_concurrent = max(1, int(max_concurrent))
        self.model = model

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._executor: Optional[ThreadPoolExecutor] = None
        self._inflight: Dict[str, Future] = {}
        self._failure_counts: Dict[str, int] = {}
        self._lock = threading.Lock()

    # ── Lifecycle ────────────────────────────────────────────────

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            logger.info("GrantScheduler already running")
            return
        self._stop_event.clear()
        self._executor = ThreadPoolExecutor(
            max_workers=self.max_concurrent, thread_name_prefix="grant-crawl"
        )
        self._thread = threading.Thread(
            target=self._loop, name="grant-scheduler", daemon=True
        )
        self._thread.start()
        logger.info(
            "GrantScheduler started (tick=%ds, max_concurrent=%d)",
            self.tick_seconds, self.max_concurrent,
        )

    def stop(self) -> None:
        self._stop_event.set()
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None
        logger.info("GrantScheduler stopped")

    def status(self) -> Dict[str, object]:
        with self._lock:
            return {
                "running": bool(self._thread and self._thread.is_alive()),
                "inflight": sorted(self._inflight.keys()),
                "failure_counts": dict(self._failure_counts),
                "tick_seconds": self.tick_seconds,
                "max_concurrent": self.max_concurrent,
            }

    # ── Manual trigger (used by API) ─────────────────────────────

    def trigger(self, source_id: str) -> bool:
        """Force-run a source crawl outside the schedule. Returns False if already running."""
        source = _get_source(source_id)
        if source is None:
            logger.warning("trigger: unknown source_id=%s", source_id)
            return False
        with self._lock:
            if source_id in self._inflight:
                return False
            self._failure_counts.pop(source_id, None)
            self._dispatch(source)
        return True

    # ── Core loop ────────────────────────────────────────────────

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception:  # noqa: BLE001
                logger.exception("Scheduler tick crashed — continuing")
            # Wait in small slices so stop() is responsive.
            for _ in range(self.tick_seconds):
                if self._stop_event.is_set():
                    return
                time.sleep(1)

    def _tick(self) -> None:
        sources = list_sources(enabled_only=True)
        now = datetime.utcnow()
        for source in sources:
            if self._stop_event.is_set():
                return
            if not self._is_due(source, now):
                continue
            with self._lock:
                if source.source_id in self._inflight:
                    continue
                # Back off sources with repeated failures (operator must re-enable via trigger).
                if self._failure_counts.get(source.source_id, 0) >= 2:
                    continue
                self._dispatch(source)

    def _dispatch(self, source: GrantSource) -> None:
        """Submit a source crawl to the worker pool. Caller holds self._lock."""
        if not self._executor:
            return
        run_id = f"run-{uuid.uuid4()}"
        started = datetime.utcnow().isoformat()
        save_crawl_run(
            run_id=run_id,
            source_id=source.source_id,
            started_at=started,
            status="running",
        )
        future = self._executor.submit(self._run_crawl, source, run_id, started)
        future.add_done_callback(lambda f, sid=source.source_id: self._on_done(sid, f))
        self._inflight[source.source_id] = future
        logger.info("scheduler: dispatched %s (run=%s)", source.source_id, run_id)

    def _run_crawl(self, source: GrantSource, run_id: str, started_at: str) -> Dict[str, object]:
        try:
            result = discover_source(source, max_pages=40, model=self.model)
            save_crawl_run(
                run_id=run_id,
                source_id=source.source_id,
                started_at=started_at,
                status="completed",
                completed_at=datetime.utcnow().isoformat(),
                new_count=len(result.opportunities),
                updated_count=0,
                errors=result.errors,
            )
            return {"ok": True, "new": len(result.opportunities), "errors": result.errors}
        except Exception as e:  # noqa: BLE001
            logger.exception("scheduler: crawl failed for %s", source.source_id)
            save_crawl_run(
                run_id=run_id,
                source_id=source.source_id,
                started_at=started_at,
                status="failed",
                completed_at=datetime.utcnow().isoformat(),
                errors=[str(e)],
            )
            return {"ok": False, "error": str(e)}

    def _on_done(self, source_id: str, future: Future) -> None:
        with self._lock:
            self._inflight.pop(source_id, None)
            try:
                result = future.result()
            except Exception as e:  # noqa: BLE001
                result = {"ok": False, "error": str(e)}

            if result.get("ok"):
                self._failure_counts.pop(source_id, None)
            else:
                self._failure_counts[source_id] = self._failure_counts.get(source_id, 0) + 1
                if self._failure_counts[source_id] >= 2:
                    try:
                        fire_source_failure(
                            source_id=source_id,
                            error=str(result.get("error") or "unknown"),
                        )
                    except Exception:  # noqa: BLE001
                        logger.exception("Failed to fire source_failure alert")

    # ── Schedule parsing ─────────────────────────────────────────

    def _is_due(self, source: GrantSource, now: datetime) -> bool:
        schedule = (source.metadata or {}).get("schedule") or "daily_02:00_utc"
        last = _latest_completion(source.source_id)
        return _schedule_is_due(schedule, now, last)


# ── Helpers (module level for testability) ──────────────────────────


def _get_source(source_id: str) -> Optional[GrantSource]:
    for src in list_sources():
        if src.source_id == source_id:
            return src
    return None


def _latest_completion(source_id: str) -> Optional[datetime]:
    """Return the most recent completed-at for a source, or None."""
    runs = list_crawl_runs(source_id=source_id, limit=1)
    if not runs:
        return None
    ts = runs[0].get("completed_at") or runs[0].get("started_at")
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:  # noqa: BLE001
        return None


def _schedule_is_due(schedule: str, now: datetime, last: Optional[datetime]) -> bool:
    """
    Pure function: returns True iff the schedule says ``now`` is a crawl slot.
    Used by the scheduler and by tests.
    """
    schedule = (schedule or "").strip().lower()

    if schedule == "hourly":
        if last is None:
            return True
        return (now - last) >= timedelta(minutes=55)

    if schedule.startswith("daily_"):
        # daily_HH:MM_utc
        try:
            body = schedule[len("daily_"):].replace("_utc", "")
            hh, mm = body.split(":")
            target_hour, target_min = int(hh), int(mm)
        except Exception:  # noqa: BLE001
            target_hour, target_min = 2, 0
        # Due if we're within 10 minutes after the scheduled time and
        # we haven't crawled since today's slot.
        slot = now.replace(hour=target_hour, minute=target_min, second=0, microsecond=0)
        if now < slot:
            return False
        # Five-minute tick window: permissive 10-minute grace so the slot
        # still fires if we miss a single tick.
        if (now - slot) > timedelta(minutes=10):
            # Outside the grace window: require that we haven't run since
            # the slot and it's not > 1 day since.
            pass
        if last is None:
            return True
        return last < slot

    if schedule.startswith("weekly_"):
        weekday_name = schedule[len("weekly_"):]
        target_weekday = _WEEKDAY_MAP.get(weekday_name)
        if target_weekday is None:
            return False
        # Due on the target weekday if we haven't run in the last 6 days.
        if now.weekday() != target_weekday:
            return False
        if last is None:
            return True
        return (now - last) >= timedelta(days=6)

    # Unknown schedule → never due (operator must trigger manually).
    return False


# ── Global singleton ────────────────────────────────────────────────


_global_scheduler: Optional[GrantScheduler] = None


def get_scheduler() -> GrantScheduler:
    global _global_scheduler
    if _global_scheduler is None:
        _global_scheduler = GrantScheduler()
    return _global_scheduler


def start_scheduler() -> GrantScheduler:
    """Idempotent helper called from app startup."""
    sched = get_scheduler()
    sched.start()
    return sched


def stop_scheduler() -> None:
    global _global_scheduler
    if _global_scheduler is not None:
        _global_scheduler.stop()
