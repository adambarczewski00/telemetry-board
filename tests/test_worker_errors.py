from __future__ import annotations

from pathlib import Path

import requests
from prometheus_client import generate_latest
from pytest import MonkeyPatch, raises


def _prep_db(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/worker_errors.db")
    from app.db import create_all

    create_all()


def test_fetch_price_unsupported_symbol_records_failure(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    _prep_db(monkeypatch, tmp_path)
    from worker.tasks.prices import fetch_price

    with raises(ValueError):
        fetch_price.run("DOGE")

    # failure metric for DOGE should be present
    metrics_text = generate_latest().decode()
    assert 'fetch_price_failure_total{symbol="DOGE"}' in metrics_text


def test_fetch_price_network_error_records_failure(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    _prep_db(monkeypatch, tmp_path)

    from worker.tasks.prices import fetch_price

    def _boom(url: str, timeout: int = 10) -> requests.Response:  # type: ignore[override]
        raise requests.RequestException("network down")

    monkeypatch.setattr(requests, "get", _boom)

    with raises(Exception):
        fetch_price.run("ETH")

    metrics_text = generate_latest().decode()
    assert 'fetch_price_failure_total{symbol="ETH"}' in metrics_text

