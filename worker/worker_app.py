from __future__ import annotations

import os
from typing import Final

from celery import Celery
from prometheus_client import start_http_server
from celery.schedules import schedule as sched
from worker.schedule import build_beat_schedule, LazyBeatSchedule

# Default local-stack broker URL; production is provided via env.
DEFAULT_BROKER: Final[str] = "redis://redis:6379/0"

celery_app = Celery("telemetry_worker")
broker_url = os.getenv("REDIS_URL", DEFAULT_BROKER)
celery_app.conf.broker_url = broker_url
celery_app.conf.result_backend = broker_url


def _enable_metrics() -> bool:
    """Allow operators to toggle the Prometheus endpoint at runtime."""
    value = os.getenv("ENABLE_WORKER_METRICS", "true")
    return value.lower() in {"1", "true", "yes", "on"}


def _start_metrics_server() -> None:
    """Run `prometheus_client`'s basic HTTP server for worker metrics."""
    port = int(os.getenv("WORKER_METRICS_PORT", "8001"))
    start_http_server(port)


if _enable_metrics():
    # Start the HTTP listener as soon as the module is imported by Celery.
    _start_metrics_server()


@celery_app.task
def ping() -> str:
    """Basic connectivity check used by tests and smoke probes."""
    return "pong"


# Ensure tasks package is imported so Celery registers them
try:
    import worker.tasks.prices  # noqa: F401
except Exception:
    # Keep the worker importable even if optional deps are missing in some envs
    pass
try:
    import worker.tasks.alerts  # noqa: F401
except Exception:
    pass
try:
    import worker.tasks.maintenance  # noqa: F401
except Exception:
    pass


def _enable_beat() -> bool:
    value = os.getenv("ENABLE_BEAT", "false")
    return value.lower() in {"1", "true", "yes", "on"}


def _parse_assets_env() -> list[str]:
    raw = os.getenv("ASSETS", "BTC,ETH")
    return [x.strip().upper() for x in raw.split(",") if x.strip()]


def _build_schedule_from_env() -> dict[str, dict]:
    if not _enable_beat():
        return {}
    interval = int(os.getenv("FETCH_INTERVAL_SECONDS", "300"))
    assets = _parse_assets_env()
    schedule = build_beat_schedule(assets, interval)
    # Retention job (optional): run daily by default
    retention_days = int(os.getenv("RETENTION_DAYS", "30"))
    if retention_days > 0:
        retention_interval = int(os.getenv("RETENTION_INTERVAL_SECONDS", "86400"))
        schedule["prune_old_prices"] = {
            "task": "prune_old_prices",
            "schedule": sched(timedelta(seconds=retention_interval)),
            "args": (retention_days,),
        }
    return schedule


# Use a lazy schedule so tests that set env after an earlier import
# still see the correct configuration when accessing the schedule.
celery_app.conf.beat_schedule = LazyBeatSchedule(_build_schedule_from_env)
