from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlalchemy.orm import Session
from sqlalchemy import select


def _client(monkeypatch: MonkeyPatch, tmp_path: Path) -> TestClient:
    from app.db import create_all
    from app.main import create_app

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test_prices_summary.db")
    create_all()
    return TestClient(create_app())


def test_price_summary_empty(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path)
    # Create asset via API
    r = client.post("/assets/", json={"symbol": "BTC"})
    assert r.status_code == 201

    r = client.get("/prices/summary", params={"asset": "BTC", "window": "24h"})
    assert r.status_code == 200
    body = r.json()
    assert body["points"] == 0
    assert body["first"] is None


def test_price_summary_stats(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path)
    # Create asset and seed price history
    r = client.post("/assets/", json={"symbol": "BTC"})
    assert r.status_code == 201

    from app.db import get_engine
    from app.models import Asset, PriceHistory

    session = Session(bind=get_engine())
    try:
        asset = session.execute(select(Asset).where(Asset.symbol == "BTC")).scalar_one()
        now = datetime.now(timezone.utc)
        session.add_all(
            [
                PriceHistory(asset_id=asset.id, ts=now - timedelta(hours=2), price=100.0),
                PriceHistory(asset_id=asset.id, ts=now - timedelta(hours=1), price=110.0),
                PriceHistory(asset_id=asset.id, ts=now - timedelta(minutes=10), price=105.0),
            ]
        )
        session.commit()
    finally:
        session.close()

    r = client.get("/prices/summary", params={"asset": "BTC", "window": "3h"})
    assert r.status_code == 200
    body = r.json()
    assert body["points"] == 3
    assert body["first"] == 100.0
    assert body["last"] == 105.0
    assert body["min"] == 100.0
    assert body["max"] == 110.0
    assert abs(body["avg"] - ((100.0 + 110.0 + 105.0) / 3)) < 1e-6

    # Narrow window to 30m – should include only the last point
    r = client.get("/prices/summary", params={"asset": "BTC", "window": "30"})
    assert r.status_code == 200
    body = r.json()
    assert body["points"] == 1
    assert body["first"] == 105.0
    assert body["last"] == 105.0


def test_price_summary_invalid_window(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path)
    # Create asset via API
    r = client.post("/assets/", json={"symbol": "BTC"})
    assert r.status_code == 201

    r = client.get("/prices/summary", params={"asset": "BTC", "window": "bad-window"})
    assert r.status_code == 400
    assert r.json()["detail"] == "invalid window"
