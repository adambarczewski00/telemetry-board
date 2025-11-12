from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import json
import logging
from prometheus_client import Counter, Histogram
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db import get_engine
from app.models import Alert, Asset, PriceHistory
from worker.worker_app import celery_app


ALERTS_TOTAL = Counter("alerts_total", "Total generated alerts", ["symbol"])
ALERT_COMPUTE_SECONDS = Histogram(
    "alert_compute_seconds", "Time spent computing alerts", ["symbol"]
)


def _settings() -> tuple[int, float]:
    window_minutes = int(os.getenv("ALERT_WINDOW_MINUTES", "60"))
    threshold_pct = float(os.getenv("ALERT_THRESHOLD_PCT", "5"))
    return window_minutes, threshold_pct


def _session() -> Session:
    return sessionmaker(
        bind=get_engine(), autoflush=False, autocommit=False, future=True
    )()


@celery_app.task(bind=True, name="compute_alerts")
def compute_alerts(
    self: object,
    symbol: str,
    window_minutes: int | None = None,
    threshold_pct: float | None = None,
) -> int:
    symbol_u = symbol.upper()
    wm, tp = _settings()
    window_m = window_minutes if window_minutes is not None else wm
    threshold = threshold_pct if threshold_pct is not None else tp

    with ALERT_COMPUTE_SECONDS.labels(symbol=symbol_u).time():
        db = _session()
        try:
            asset = db.execute(
                select(Asset).where(Asset.symbol == symbol_u)
            ).scalar_one_or_none()
            if asset is None:
                return 0

            # Prefer per-asset overrides when available
            if asset.alert_window_min is not None and window_minutes is None:
                window_m = int(asset.alert_window_min)
            if asset.alert_pct is not None and threshold_pct is None:
                try:
                    threshold = float(asset.alert_pct)  # Numeric -> float
                except Exception:
                    pass

            now = datetime.now(timezone.utc)
            start = now - timedelta(minutes=window_m)

            rows = (
                db.execute(
                    select(PriceHistory)
                    .where(PriceHistory.asset_id == asset.id, PriceHistory.ts >= start)
                    .order_by(PriceHistory.ts.asc())
                )
                .scalars()
                .all()
            )

            if len(rows) < 2:
                return 0

            first = rows[0]
            last = rows[-1]
            if float(first.price) == 0.0:
                return 0

            change_pct = (
                (float(last.price) - float(first.price)) / float(first.price) * 100.0
            )
            if abs(change_pct) >= threshold:
                alert = Alert(
                    asset_id=asset.id,
                    triggered_at=now,
                    window_minutes=window_m,
                    change_pct=change_pct,
                )
                db.add(alert)
                db.commit()
                ALERTS_TOTAL.labels(symbol=symbol_u).inc()
                # Structured JSON log for alert event
                try:
                    payload = {
                        "ts": now.isoformat(),
                        "lvl": "info",
                        "event": "alert_created",
                        "asset": symbol_u,
                        "window_minutes": window_m,
                        "change_pct": float(change_pct),
                        "threshold_pct": float(threshold),
                    }
                    logging.getLogger(__name__).info(json.dumps(payload))
                except Exception:
                    # logging must not break the task
                    pass
                return 1
            return 0
        finally:
            db.close()
