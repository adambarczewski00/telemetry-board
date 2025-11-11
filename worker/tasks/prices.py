from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping
import time

import requests
from prometheus_client import Counter, Histogram
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import select

from app.db import get_engine
from app.models import Asset, PriceHistory
from worker.worker_app import celery_app


FETCH_SUCCESS = Counter(
    "fetch_price_success_total", "Successful price fetches", ["symbol"]
)
FETCH_FAILURE = Counter("fetch_price_failure_total", "Failed price fetches", ["symbol"])
FETCH_DURATION = Histogram(
    "fetch_price_duration_seconds", "Duration of price fetches", ["symbol"]
)


def _coingecko_id_for_symbol(symbol: str) -> str | None:
    mapping = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
    }
    return mapping.get(symbol.upper())


def _get_price_usd(symbol: str) -> float:
    cg_id = _coingecko_id_for_symbol(symbol)
    if cg_id is None:
        raise ValueError("unsupported asset symbol")
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={cg_id}&vs_currencies=usd"
    # Minimal, stable backoff on transient errors (429/5xx)
    delays = [1, 2, 4]
    last_exc: Exception | None = None
    for attempt, delay in enumerate([0] + delays):
        try:
            resp = requests.get(url, timeout=10)
            # If status indicates transient issue, raise to trigger retry
            if resp.status_code in (429,) or resp.status_code >= 500:
                resp.raise_for_status()
            resp.raise_for_status()
            data: Mapping[str, Any] = resp.json()
            price = float(data[cg_id]["usd"])  # type: ignore[index]
            return price
        except Exception as e:  # pragma: no cover - branches tested via monkeypatch
            last_exc = e
            if attempt == len(delays):
                break
            time.sleep(delay)
    assert last_exc is not None
    raise last_exc


def _get_market_chart_usd(symbol: str, hours: int = 24) -> list[tuple[datetime, float]]:
    """Fetch historical price points for the given symbol.

    Uses CoinGecko market_chart endpoint. Returns list of (ts, price) tuples
    in UTC, filtered to the last `hours` hours.
    """
    cg_id = _coingecko_id_for_symbol(symbol)
    if cg_id is None:
        raise ValueError("unsupported asset symbol")
    # CoinGecko accepts fractional days; use 1 for <=24h, ceil for more.
    days = max(1.0, hours / 24.0)
    url = (
        f"https://api.coingecko.com/api/v3/coins/{cg_id}/market_chart?vs_currency=usd&days={days}&interval=minute"
    )
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    series = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    for ts_ms, price in data.get("prices", []):  # type: ignore[assignment]
        ts = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
        if ts >= cutoff:
            series.append((ts, float(price)))
    return series


def _session() -> Session:
    return sessionmaker(
        bind=get_engine(), autoflush=False, autocommit=False, future=True
    )()


@celery_app.task(bind=True, name="fetch_price")
def fetch_price(self: object, symbol: str) -> float:
    symbol_u = symbol.upper()
    with FETCH_DURATION.labels(symbol=symbol_u).time():
        try:
            price = _get_price_usd(symbol_u)
        except Exception:
            FETCH_FAILURE.labels(symbol=symbol_u).inc()
            raise

    # Persist to DB
    db = _session()
    try:
        asset = db.execute(
            select(Asset).where(Asset.symbol == symbol_u)
        ).scalar_one_or_none()
        if asset is None:
            # auto-create minimal asset record to avoid dropped samples in demo
            asset = Asset(symbol=symbol_u, name=None)
            db.add(asset)
            db.commit()
            db.refresh(asset)
        ph = PriceHistory(asset_id=asset.id, ts=datetime.now(timezone.utc), price=price)
        db.add(ph)
        db.commit()
    finally:
        db.close()

    FETCH_SUCCESS.labels(symbol=symbol_u).inc()
    return price


@celery_app.task(bind=True, name="backfill_prices")
def backfill_prices(self: object, symbol: str, hours: int = 24) -> int:
    """Backfill recent price history for an asset.

    Returns the number of points inserted. Safe to run multiple times; duplicates
    are ignored thanks to the unique constraint on (asset_id, ts).
    """
    symbol_u = symbol.upper()
    # Ensure tables exist in dev/compose scenarios
    try:
        from app.db import create_all

        create_all()
    except Exception:
        pass

    points = _get_market_chart_usd(symbol_u, hours=hours)

    db = _session()
    inserted = 0
    try:
        asset = db.execute(select(Asset).where(Asset.symbol == symbol_u)).scalar_one_or_none()
        if asset is None:
            asset = Asset(symbol=symbol_u, name=None)
            db.add(asset)
            db.commit()
            db.refresh(asset)

        for ts, price in points:
            ph = PriceHistory(asset_id=asset.id, ts=ts, price=price)
            db.add(ph)
            try:
                db.commit()
                inserted += 1
            except Exception:
                # Likely unique constraint violation; drop and continue
                db.rollback()
        return inserted
    finally:
        db.close()
