from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from pytest import MonkeyPatch


def _client_with_db(monkeypatch: MonkeyPatch, tmp_path: Path) -> TestClient:
    # Point the application to a temporary SQLite DB file.
    db_url = f"sqlite:///{tmp_path}/test_assets.db"
    monkeypatch.setenv("DATABASE_URL", db_url)

    # Import inside to ensure env var is applied before engine creation.
    from app.db import create_all
    from app.main import create_app

    # Create schema for tests.
    create_all()
    return TestClient(create_app())


def test_get_assets_empty(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    client = _client_with_db(monkeypatch, tmp_path)
    resp = client.get("/assets/")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_asset_valid(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    client = _client_with_db(monkeypatch, tmp_path)
    payload = {"symbol": "btc", "name": "Bitcoin"}
    resp = client.post("/assets/", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["symbol"] == "BTC"
    assert body["name"] == "Bitcoin"
    assert isinstance(body["id"], int)


def test_create_asset_duplicate(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    client = _client_with_db(monkeypatch, tmp_path)
    resp1 = client.post("/assets/", json={"symbol": "ETH", "name": "Ethereum"})
    assert resp1.status_code == 201
    resp2 = client.post("/assets/", json={"symbol": "eth", "name": "Ethereum"})
    assert resp2.status_code == 409


def test_create_asset_validation(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    client = _client_with_db(monkeypatch, tmp_path)
    # too short symbol
    resp = client.post("/assets/", json={"symbol": "X"})
    assert resp.status_code == 422
