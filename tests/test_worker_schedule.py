from __future__ import annotations

from pathlib import Path

from pytest import MonkeyPatch


def test_builds_schedule_from_env(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    # Avoid starting the metrics HTTP server
    monkeypatch.setenv("ENABLE_WORKER_METRICS", "false")
    monkeypatch.setenv("ENABLE_BEAT", "true")
    monkeypatch.setenv("ASSETS", "BTC, eth ,  ")
    monkeypatch.setenv("FETCH_INTERVAL_SECONDS", "120")

    from worker.worker_app import celery_app

    schedule = celery_app.conf.beat_schedule
    # keys and structure
    assert "fetch_BTC" in schedule
    assert "fetch_ETH" in schedule
    assert schedule["fetch_BTC"]["task"] == "fetch_price"
    assert schedule["fetch_BTC"]["args"] == ("BTC",)

