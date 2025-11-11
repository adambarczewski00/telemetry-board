from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from pytest import MonkeyPatch


def _client(monkeypatch: MonkeyPatch, tmp_path: Path) -> TestClient:
    from app.db import create_all
    from app.main import create_app

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test_prices.db")
    create_all()
    return TestClient(create_app())


def _create_asset(client: TestClient, symbol: str) -> None:
    resp = client.post("/assets/", json={"symbol": symbol})
    assert resp.status_code == 201


def test_get_prices_empty(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path)
    _create_asset(client, "BTC")
    resp = client.get("/prices/", params={"asset": "BTC"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_prices_invalid_asset(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path)
    resp = client.get("/prices/", params={"asset": "NOPE"})
    assert resp.status_code == 404


def test_get_prices_window_param(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path)
    _create_asset(client, "ETH")
    resp = client.get("/prices/", params={"asset": "ETH", "window": "24h"})
    assert resp.status_code == 200
    assert resp.json() == []
