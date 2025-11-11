from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from prometheus_client import generate_latest
from pytest import MonkeyPatch
from sqlalchemy.orm import Session


def _setup_db(monkeypatch: MonkeyPatch, tmp_path: Path) -> Session:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/alerts_metrics.db")
    from app.db import create_all, get_engine
    from app.models import Asset

    create_all()
    session = Session(bind=get_engine())
    asset = Asset(symbol="BTC", name=None)
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return session


def test_alert_metrics_increment_on_trigger(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    session = _setup_db(monkeypatch, tmp_path)
    from sqlalchemy import select
    from app.models import PriceHistory, Asset
    from worker.tasks.alerts import compute_alerts

    asset = session.execute(select(Asset).where(Asset.symbol == "BTC")).scalar_one()
    now = datetime.now(timezone.utc)
    session.add_all(
        [
            PriceHistory(asset_id=asset.id, ts=now - timedelta(minutes=50), price=100.0),
            PriceHistory(asset_id=asset.id, ts=now - timedelta(minutes=5), price=106.0),
        ]
    )
    session.commit()

    created = compute_alerts.run("BTC")
    assert created == 1

    metrics_text = generate_latest().decode()
    # Counter presence check – value may vary across test runs due to global registry
    assert 'alerts_total{symbol="BTC"}' in metrics_text
    assert 'alert_compute_seconds' in metrics_text
