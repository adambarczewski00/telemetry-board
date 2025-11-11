from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from pytest import MonkeyPatch
from sqlalchemy import select
from sqlalchemy.orm import Session


def _setup_db(monkeypatch: MonkeyPatch, tmp_path: Path) -> Session:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/alerts_compute.db")
    from app.db import create_all, get_engine
    from app.models import Asset

    create_all()
    session = Session(bind=get_engine())
    asset = Asset(symbol="BTC", name=None)
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return session


def test_compute_alerts_triggers_when_threshold_met(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    session = _setup_db(monkeypatch, tmp_path)
    from app.models import PriceHistory, Alert, Asset
    from worker.tasks.alerts import compute_alerts

    asset = session.execute(select(Asset).where(Asset.symbol == "BTC")).scalar_one()
    now = datetime.now(timezone.utc)
    # +6% over the window
    session.add_all(
        [
            PriceHistory(asset_id=asset.id, ts=now - timedelta(minutes=50), price=100.0),
            PriceHistory(asset_id=asset.id, ts=now - timedelta(minutes=5), price=106.0),
        ]
    )
    session.commit()

    # Defaults: window 60, threshold 5
    created = compute_alerts.run("BTC")
    assert created == 1

    alerts = session.execute(select(Alert).where(Alert.asset_id == asset.id)).scalars().all()
    assert len(alerts) == 1
    assert alerts[0].window_minutes == 60
    assert float(alerts[0].change_pct) > 5.0


def test_compute_alerts_no_trigger_below_threshold(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    session = _setup_db(monkeypatch, tmp_path)
    from app.models import PriceHistory, Alert, Asset
    from worker.tasks.alerts import compute_alerts

    asset = session.execute(select(Asset).where(Asset.symbol == "BTC")).scalar_one()
    now = datetime.now(timezone.utc)
    # +4% only
    session.add_all(
        [
            PriceHistory(asset_id=asset.id, ts=now - timedelta(minutes=50), price=100.0),
            PriceHistory(asset_id=asset.id, ts=now - timedelta(minutes=5), price=104.0),
        ]
    )
    session.commit()

    created = compute_alerts.run("BTC")
    assert created == 0

    alerts = session.execute(select(Alert).where(Alert.asset_id == asset.id)).scalars().all()
    assert len(alerts) == 0


def test_compute_alerts_respects_env_threshold(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    session = _setup_db(monkeypatch, tmp_path)
    from app.models import PriceHistory, Alert, Asset
    from worker.tasks.alerts import compute_alerts

    # Lower threshold to 3% so a 4% move triggers
    monkeypatch.setenv("ALERT_THRESHOLD_PCT", "3")

    asset = session.execute(select(Asset).where(Asset.symbol == "BTC")).scalar_one()
    now = datetime.now(timezone.utc)
    session.add_all(
        [
            PriceHistory(asset_id=asset.id, ts=now - timedelta(minutes=50), price=100.0),
            PriceHistory(asset_id=asset.id, ts=now - timedelta(minutes=5), price=104.0),
        ]
    )
    session.commit()

    created = compute_alerts.run("BTC")
    assert created == 1

    alerts = session.execute(select(Alert).where(Alert.asset_id == asset.id)).scalars().all()
    assert len(alerts) == 1


def test_compute_alerts_respects_env_window(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    session = _setup_db(monkeypatch, tmp_path)
    from app.models import PriceHistory, Alert, Asset
    from worker.tasks.alerts import compute_alerts

    # Narrow window to exclude the first sample; only one point remains → no alert
    monkeypatch.setenv("ALERT_WINDOW_MINUTES", "30")

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
    assert created == 0

    alerts = session.execute(select(Alert).where(Alert.asset_id == asset.id)).scalars().all()
    assert len(alerts) == 0
