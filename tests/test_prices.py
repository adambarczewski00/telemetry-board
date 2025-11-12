from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlalchemy import select
from sqlalchemy.orm import Session


def _client(monkeypatch: MonkeyPatch, tmp_path: Path) -> TestClient:
    from app.db import create_all
    from app.main import create_app

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test_prices.db")
    create_all()
    return TestClient(create_app())


def _create_asset(client: TestClient, symbol: str) -> int:
    resp = client.post("/assets/", json={"symbol": symbol})
    assert resp.status_code == 201
    return int(resp.json()["id"])  # type: ignore[return-value]


def test_get_prices_window_minutes_filters(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    from app.db import get_engine
    from app.models import Asset, PriceHistory

    client = _client(monkeypatch, tmp_path)
    _create_asset(client, "BTC")

    # Seed price history: one old (90m), one recent (5m)
    session = Session(bind=get_engine())
    try:
        asset = session.execute(select(Asset).where(Asset.symbol == "BTC")).scalar_one()
        now = datetime.now(timezone.utc)
        session.add_all(
            [
                PriceHistory(asset_id=asset.id, ts=now - timedelta(minutes=90), price=100.0),
                PriceHistory(asset_id=asset.id, ts=now - timedelta(minutes=5), price=105.0),
            ]
        )
        session.commit()
    finally:
        session.close()

    # Only the recent point should be included with window=60 (minutes)
    resp = client.get("/prices/", params={"asset": "BTC", "window": "60"})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert float(data[0]["price"]) == 105.0


def test_get_prices_invalid_window_returns_400(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    client = _client(monkeypatch, tmp_path)
    _create_asset(client, "BTC")

    resp = client.get("/prices/", params={"asset": "BTC", "window": "not-a-window"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "invalid window"

