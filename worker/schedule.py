from __future__ import annotations

from datetime import timedelta
from typing import Dict, List

from celery.schedules import schedule as sched


def build_beat_schedule(assets: List[str], every_seconds: int) -> Dict[str, dict]:
    """Build a Celery beat schedule for periodic price fetches.

    Each asset gets an entry invoking the `fetch_price` task every N seconds.
    """
    seconds = max(1, int(every_seconds))
    normalized = [a.strip().upper() for a in assets if a.strip()]
    return {
        f"fetch_{sym}": {
            "task": "fetch_price",
            "schedule": sched(timedelta(seconds=seconds)),
            "args": (sym,),
        }
        for sym in normalized
    }

