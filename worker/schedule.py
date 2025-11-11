from __future__ import annotations

from datetime import timedelta
from typing import Callable, Dict, List, Mapping, Iterator, Optional

from celery.schedules import schedule as sched


def build_beat_schedule(assets: List[str], every_seconds: int) -> Dict[str, dict]:
    """Build a Celery beat schedule for periodic price fetches.

    Each asset gets an entry invoking the `fetch_price` task every N seconds.
    """
    seconds = max(1, int(every_seconds))
    normalized = [a.strip().upper() for a in assets if a.strip()]
    schedule: Dict[str, dict] = {}
    for sym in normalized:
        schedule[f"fetch_{sym}"] = {
            "task": "fetch_price",
            "schedule": sched(timedelta(seconds=seconds)),
            "args": (sym,),
        }
        # Also compute alerts on the same cadence (simple MVP assumption)
        schedule[f"compute_{sym}"] = {
            "task": "compute_alerts",
            "schedule": sched(timedelta(seconds=seconds)),
            "args": (sym,),
        }
    return schedule


class LazyBeatSchedule(Mapping[str, dict]):
    """A mapping that builds the beat schedule on first access.

    This helps tests that set environment variables after an early import of
    the worker module by deferring schedule construction until it is actually
    read. The provided factory should read any necessary environment variables
    and return a plain dict mapping.
    """

    def __init__(self, factory: Callable[[], Dict[str, dict]]):
        self._factory = factory
        self._cache: Optional[Dict[str, dict]] = None

    def _ensure(self) -> None:
        if self._cache is None:
            self._cache = self._factory()

    def refresh(self) -> None:
        """Clear the cache so the next access recomputes the schedule."""
        self._cache = None

    def __getitem__(self, key: str) -> dict:
        self._ensure()
        assert self._cache is not None
        return self._cache[key]

    def __iter__(self) -> Iterator[str]:
        self._ensure()
        assert self._cache is not None
        return iter(self._cache)

    def __len__(self) -> int:
        self._ensure()
        assert self._cache is not None
        return len(self._cache)

    def __contains__(self, key: object) -> bool:  # type: ignore[override]
        self._ensure()
        assert self._cache is not None
        return key in self._cache
