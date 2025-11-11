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


def test_fetch_price_inserts_price(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    # point DB to a temp sqlite file
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/worker_fetch.db")

    # create schema
    from app.db import create_all, get_engine
    from sqlalchemy.orm import Session
    from sqlalchemy import select
    from app.models import Asset, PriceHistory

    create_all()

    # create asset row
    db = Session(bind=get_engine())
    asset = Asset(symbol="BTC", name=None)
    db.add(asset)
    db.commit()
    db.refresh(asset)

    # mock requests.get
    def _fake_get(url: str, timeout: int = 10) -> _Resp:  # type: ignore[override]
        assert "bitcoin" in url
        return _Resp({"bitcoin": {"usd": 12345.67}})

    import requests

    monkeypatch.setattr(requests, "get", _fake_get)

    # run task synchronously
    from worker.tasks.prices import fetch_price

    result = fetch_price.run("BTC")
    assert result == 12345.67

    # verify DB insert
    count = (
        db.execute(select(PriceHistory).where(PriceHistory.asset_id == asset.id))
        .scalars()
        .all()
    )
    assert len(count) == 1
