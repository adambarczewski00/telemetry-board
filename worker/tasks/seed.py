from __future__ import annotations

import os
import random
from datetime import datetime, timedelta, timezone
from typing import Iterator

from sqlalchemy import select, func
from sqlalchemy.orm import Session, sessionmaker

from app.db import get_engine
from app.models import Asset, PriceHistory
from worker.worker_app import celery_app


def _session() -> Session:
    return sessionmaker(
        bind=get_engine(), autoflush=False, autocommit=False, future=True
    )()


def _baseline_for_symbol(symbol: str) -> float:
    mapping = {"BTC": 50000.0, "ETH": 2000.0}
    return mapping.get(symbol.upper(), 100.0)


def _gen_series(
    start: datetime, end: datetime, interval_seconds: int, base: float, seed: int
) -> Iterator[tuple[datetime, float]]:
    rnd = random.Random(seed)
    t = start
    price = base
    drift = (rnd.random() - 0.5) * 0.001  # tiny drift
    while t <= end:
        # random walk around base with bounded noise
        noise = (rnd.random() - 0.5) * 0.02  # +/-1%
        price = max(0.01, price * (1.0 + drift + noise))
        yield (t, float(price))
        t = t + timedelta(seconds=interval_seconds)


@celery_app.task(bind=True, name="seed_mock_prices")
def seed_mock_prices(
    self: object,
    symbol: str,
    hours: int | None = None,
    interval_seconds: int | None = None,
) -> int:
    """Seed synthetic price history if asset has little or no data.

    Intended for portfolio/demos. Ensures there is at least `hours` of history;
    if the earliest sample is newer than (now - hours), it fills the gap with
    synthetic data. Uses a deterministic random walk per symbol.
    """
    sym = symbol.upper()
    hrs = int(hours or int(os.getenv("MOCK_SEED_HOURS", "168")))
    step = int(interval_seconds or int(os.getenv("MOCK_SEED_INTERVAL_SECONDS", "300")))

    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=hrs)

    db = _session()
    inserted = 0
    try:
        asset = db.execute(
            select(Asset).where(Asset.symbol == sym)
        ).scalar_one_or_none()
        if asset is None:
            asset = Asset(symbol=sym, name=None)
            db.add(asset)
            db.commit()
            db.refresh(asset)

        oldest = db.execute(
            select(func.min(PriceHistory.ts)).where(PriceHistory.asset_id == asset.id)
        ).scalar_one()
        if oldest is not None and oldest.tzinfo is None:
            # Normalize to UTC if SQLite produced naive datetimes
            oldest = oldest.replace(tzinfo=timezone.utc)
        # Seed only if there is not enough historical coverage
        if oldest is not None and oldest <= start:
            return 0

        base = _baseline_for_symbol(sym)
        seed = sum(ord(c) for c in sym)
        for ts, price in _gen_series(start, now, step, base, seed):
            ph = PriceHistory(asset_id=asset.id, ts=ts, price=price)
            db.add(ph)
            try:
                db.commit()
                inserted += 1
            except Exception:
                db.rollback()
        return inserted
    finally:
        db.close()
