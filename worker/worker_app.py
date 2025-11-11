from __future__ import annotations

import os
from typing import Final

from celery import Celery
from prometheus_client import start_http_server
from worker.schedule import build_beat_schedule

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


def _enable_beat() -> bool:
    value = os.getenv("ENABLE_BEAT", "false")
    return value.lower() in {"1", "true", "yes", "on"}


def _parse_assets_env() -> list[str]:
    raw = os.getenv("ASSETS", "BTC,ETH")
    return [x.strip().upper() for x in raw.split(",") if x.strip()]


def _configure_beat() -> None:
    if not _enable_beat():
        return
    interval = int(os.getenv("FETCH_INTERVAL_SECONDS", "300"))
    assets = _parse_assets_env()
    celery_app.conf.beat_schedule = build_beat_schedule(assets, interval)


_configure_beat()
