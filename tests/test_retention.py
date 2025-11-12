from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from pytest import MonkeyPatch
from sqlalchemy.orm import Session
from sqlalchemy import select


def _setup_db(monkeypatch: MonkeyPatch, tmp_path: Path) -> Session:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/retention.db")
    from app.db import create_all, get_engine
    create_all()
    return Session(bind=get_engine())


def test_prune_old_prices_removes_rows(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    from app.models import Asset, PriceHistory
    from worker.tasks.maintenance import prune_old_prices

    session = _setup_db(monkeypatch, tmp_path)
    try:
        asset = Asset(symbol="BTC", name=None)
        session.add(asset)
        session.commit()
        session.refresh(asset)

        now = datetime.now(timezone.utc)
        # Two old (31d), one recent (1d)
        session.add_all(
            [
                PriceHistory(asset_id=asset.id, ts=now - timedelta(days=31), price=100.0),
                PriceHistory(asset_id=asset.id, ts=now - timedelta(days=40), price=101.0),
                PriceHistory(asset_id=asset.id, ts=now - timedelta(days=1), price=102.0),
            ]
        )
        session.commit()

        # Use default RETENTION_DAYS=30
        removed = prune_old_prices.run()  # type: ignore[attr-defined]
        assert removed == 2

        remaining = (
            session.execute(select(PriceHistory).order_by(PriceHistory.ts)).scalars().all()
        )
        assert len(remaining) == 1
        assert float(remaining[0].price) == 102.0
    finally:
        session.close()


def test_prune_old_prices_disabled_with_zero(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    from worker.tasks.maintenance import prune_old_prices

    # RETENTION_DAYS <= 0 disables pruning
    monkeypatch.setenv("RETENTION_DAYS", "0")
    removed = prune_old_prices.run()  # type: ignore[attr-defined]
    assert removed == 0

