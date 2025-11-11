from __future__ import annotations

from pathlib import Path
from typing import Any

from pytest import MonkeyPatch


class _Resp:
    def __init__(self, data: dict[str, Any], status_code: int = 200) -> None:
        self._data = data
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("http error")

    def json(self) -> dict[str, Any]:
        return self._data


def test_fetch_price_retries_then_succeeds(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    # temp DB
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/worker_backoff.db")
    from app.db import create_all, get_engine
    from sqlalchemy.orm import Session
    from app.models import Asset, PriceHistory

    create_all()
    db = Session(bind=get_engine())
    db.add(Asset(symbol="BTC", name=None))
    db.commit()

    calls = {"n": 0}

    def _fake_get(url: str, timeout: int = 10) -> _Resp:  # type: ignore[override]
        calls["n"] += 1
        if calls["n"] < 3:
            return _Resp({}, status_code=500)
        return _Resp({"bitcoin": {"usd": 123.45}}, status_code=200)

    import requests, time

    monkeypatch.setattr(requests, "get", _fake_get)
    monkeypatch.setattr(time, "sleep", lambda s: None)

    from worker.tasks.prices import fetch_price

    out = fetch_price.run("BTC")
    assert out == 123.45
    assert calls["n"] == 3

    rows = db.query(PriceHistory).all()
    assert len(rows) == 1


def test_fetch_price_retries_and_fails(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/worker_backoff_fail.db")
    from app.db import create_all, get_engine
    from sqlalchemy.orm import Session
    from app.models import Asset, PriceHistory

    create_all()
    db = Session(bind=get_engine())
    db.add(Asset(symbol="BTC", name=None))
    db.commit()

    def _fake_get(url: str, timeout: int = 10) -> _Resp:  # type: ignore[override]
        return _Resp({}, status_code=500)

    import requests, time

    monkeypatch.setattr(requests, "get", _fake_get)
    monkeypatch.setattr(time, "sleep", lambda s: None)

    from worker.tasks.prices import fetch_price

    try:
        fetch_price.run("BTC")
        assert False, "expected failure"
    except Exception:
        pass

    rows = db.query(PriceHistory).all()
    assert len(rows) == 0

