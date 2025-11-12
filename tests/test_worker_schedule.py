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


def test_schedule_does_not_include_backfill(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ENABLE_WORKER_METRICS", "false")
    monkeypatch.setenv("ENABLE_BEAT", "true")
    monkeypatch.setenv("ASSETS", "BTC")
    monkeypatch.setenv("FETCH_INTERVAL_SECONDS", "60")
    # Even if envs are set, backfill isn’t scheduled in portfolio mode
    monkeypatch.setenv("BACKFILL_HOURS", "168")
    monkeypatch.setenv("BACKFILL_CHECK_SECONDS", "300")

    from worker.worker_app import celery_app

    schedule = celery_app.conf.beat_schedule
    assert not any(k.startswith("ensure_backfill_") for k in schedule)
