from __future__ import annotations
from celery import Celery

celery_app = Celery("telemetry_worker")
celery_app.conf.broker_url = "redis://redis:6379/0"
celery_app.conf.result_backend = "redis://redis:6379/0"


@celery_app.task
def ping() -> str:
    return "pong"
