from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from pytest import MonkeyPatch


def test_prices_after_worker_fetch(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    # set DB and create schema
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/api_integration.db")
    from app.db import create_all
    from app.main import create_app
    from worker.tasks.prices import fetch_price

    create_all()

    # mock price to deterministic value
    import requests

    class _Resp:
        def __init__(self, data: dict[str, object]) -> None:
            self._data = data
            self.status_code = 200

        def raise_for_status(self) -> None:  # pragma: no cover - always OK here
            return None

        def json(self) -> dict[str, object]:
            return self._data

    def _fake_get(url: str, timeout: int = 10) -> _Resp:  # type: ignore[override]
        assert "bitcoin" in url
        return _Resp({"bitcoin": {"usd": 100.0}})

    monkeypatch.setattr(requests, "get", _fake_get)

    # run task to insert a price point
    result = fetch_price.run("BTC")
    assert result == 100.0

    # query API
    client = TestClient(create_app())
    resp = client.get("/prices/", params={"asset": "BTC"})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list) and len(data) == 1
    assert abs(float(data[0]["price"]) - 100.0) < 1e-6

