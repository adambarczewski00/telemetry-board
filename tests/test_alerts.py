from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from pytest import MonkeyPatch


def _client(monkeypatch: MonkeyPatch, tmp_path: Path) -> TestClient:
    from app.db import create_all
    from app.main import create_app

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test_alerts.db")
    create_all()
    return TestClient(create_app())


def _create_asset(client: TestClient, symbol: str) -> None:
    resp = client.post("/assets/", json={"symbol": symbol})
    assert resp.status_code == 201


def test_get_alerts_empty(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path)
    _create_asset(client, "BTC")
    resp = client.get("/alerts/", params={"asset": "BTC"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_alerts_invalid_asset(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path)
    resp = client.get("/alerts/", params={"asset": "NOPE"})
    assert resp.status_code == 404


def test_get_alerts_limit_and_order(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    from datetime import datetime, timedelta, timezone
    from sqlalchemy.orm import Session
    from sqlalchemy import select
    from app.db import get_engine
    from app.models import Asset, Alert

    client = _client(monkeypatch, tmp_path)

    # Ensure asset exists via API
    _create_asset(client, "BTC")

    # Insert multiple alerts with different timestamps
    session = Session(bind=get_engine())
    try:
        asset = session.execute(select(Asset).where(Asset.symbol == "BTC")).scalar_one()
        now = datetime.now(timezone.utc)
        session.add_all(
            [
                Alert(asset_id=asset.id, triggered_at=now - timedelta(minutes=10), window_minutes=60, change_pct=3.0),
                Alert(asset_id=asset.id, triggered_at=now - timedelta(minutes=5), window_minutes=60, change_pct=4.0),
                Alert(asset_id=asset.id, triggered_at=now - timedelta(minutes=1), window_minutes=60, change_pct=5.0),
            ]
        )
        session.commit()
    finally:
        session.close()

    # Limit to 2 – should return the two most recent in desc order
    resp = client.get("/alerts/", params={"asset": "BTC", "limit": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    # Desc order by triggered_at: latest first (change_pct 5.0 then 4.0)
    assert body[0]["change_pct"] == 5.0
    assert body[1]["change_pct"] == 4.0
