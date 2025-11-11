from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from pytest import MonkeyPatch
from sqlalchemy.orm import Session
from sqlalchemy import select


def test_prune_old_prices_removes_older_rows(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/retention.db")
    from app.db import create_all, get_engine
    from app.models import Asset, PriceHistory
    from worker.tasks.maintenance import prune_old_prices

    create_all()
    session = Session(bind=get_engine())
    try:
        asset = Asset(symbol="BTC", name=None)
        session.add(asset)
        session.commit()
        session.refresh(asset)

        now = datetime.now(timezone.utc)
        # One old (40d), one recent (5d)
        session.add_all(
            [
                PriceHistory(asset_id=asset.id, ts=now - timedelta(days=40), price=100.0),
                PriceHistory(asset_id=asset.id, ts=now - timedelta(days=5), price=110.0),
            ]
        )
        session.commit()

        deleted = prune_old_prices.run(30)
        assert deleted == 1

        rows = session.execute(select(PriceHistory)).scalars().all()
        assert len(rows) == 1
        assert float(rows[0].price) == 110.0
    finally:
        session.close()

