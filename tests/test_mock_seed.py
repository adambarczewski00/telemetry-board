from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pytest import MonkeyPatch
from sqlalchemy import select
from sqlalchemy.orm import Session


def _setup(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    from app.db import create_all

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test_mockseed.db")
    create_all()


def test_seed_mock_prices_inserts_when_empty(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    from app.db import get_engine
    from app.models import Asset, PriceHistory
    from worker.tasks.seed import seed_mock_prices

    _setup(monkeypatch, tmp_path)

    inserted = seed_mock_prices.run(symbol="BTC", hours=2, interval_seconds=300)
    assert inserted > 0

    session = Session(bind=get_engine())
    try:
        asset = session.execute(select(Asset).where(Asset.symbol == "BTC")).scalar_one()
        rows = (
            session.execute(
                select(PriceHistory).where(PriceHistory.asset_id == asset.id)
            )
            .scalars()
            .all()
        )
        assert len(rows) == inserted
        # Earliest ts ~ now - 2h (allow small delta)
        mn = min(r.ts for r in rows)
        delta = datetime.now(timezone.utc) - mn
        assert 0 < delta.total_seconds() <= 2 * 3600 + 60
    finally:
        session.close()


def test_seed_mock_prices_noop_when_data_present(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    from worker.tasks.seed import seed_mock_prices

    _setup(monkeypatch, tmp_path)

    # First seed
    first = seed_mock_prices.run(symbol="ETH", hours=1, interval_seconds=300)
    assert first > 0
    # Second call should be a no-op (returns 0)
    second = seed_mock_prices.run(symbol="ETH", hours=1, interval_seconds=300)
    assert second == 0
