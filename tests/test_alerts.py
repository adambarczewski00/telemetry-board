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

