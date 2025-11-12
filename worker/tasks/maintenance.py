from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, cast

from sqlalchemy import delete
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session, sessionmaker

from app.db import get_engine
from app.models import PriceHistory
from worker.worker_app import celery_app


def _session() -> Session:
    return sessionmaker(
        bind=get_engine(), autoflush=False, autocommit=False, future=True
    )()


def _retention_days_from_env() -> int:
    return int(os.getenv("RETENTION_DAYS", "30"))


@celery_app.task(bind=True, name="prune_old_prices")
def prune_old_prices(self: object, retention_days: int | None = None) -> int:
    days = retention_days if retention_days is not None else _retention_days_from_env()
    if days <= 0:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    session = _session()
    try:
        result = cast(
            "CursorResult[Any]",
            session.execute(delete(PriceHistory).where(PriceHistory.ts < cutoff)),
        )
        session.commit()
        # SQLAlchemy 2.0 returns rowcount on the result; fallback to 0 if None
        return int(result.rowcount or 0)
    finally:
        session.close()
