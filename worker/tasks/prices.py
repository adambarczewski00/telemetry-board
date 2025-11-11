from __future__ import annotations
from datetime import datetime, timezone
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
