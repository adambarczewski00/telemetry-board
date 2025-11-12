from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Asset, PriceHistory


class PricePoint(BaseModel):
    ts: datetime
    price: float

    model_config = ConfigDict(from_attributes=True)


router = APIRouter(prefix="/prices", tags=["prices"])


@router.get("/", response_model=List[PricePoint])
def get_prices(
    asset: str = Query(..., min_length=2, max_length=20),
    window: str | None = Query(None, description="e.g., 24h, 1h, 7d or minutes"),
    db: Session = Depends(get_session),
) -> List[PricePoint]:
    symbol = asset.upper()
    asset_row = db.execute(
        select(Asset).where(Asset.symbol == symbol)
    ).scalar_one_or_none()
    if asset_row is None:
        raise HTTPException(status_code=404, detail="asset not found")

    cutoff: Optional[datetime] = None
    if window:
        try:
            cutoff = _parse_window_to_cutoff(window)
        except Exception:
            raise HTTPException(status_code=400, detail="invalid window")

    q = select(PriceHistory).where(PriceHistory.asset_id == asset_row.id)
    if cutoff is not None:
        q = q.where(PriceHistory.ts >= cutoff)
    q = q.order_by(PriceHistory.ts)
    rows = db.execute(q).scalars().all()
    return [PricePoint.model_validate(r) for r in rows]


class PriceSummary(BaseModel):
    points: int
    first: float | None
    last: float | None
    min: float | None
    max: float | None
    avg: float | None


def _parse_window_to_cutoff(window: str) -> datetime:
    now = datetime.now(timezone.utc)
    w = window.strip().lower()
    if w.endswith("h"):
        hours = int(w[:-1])
        return now - timedelta(hours=hours)
    if w.endswith("d"):
        days = int(w[:-1])
        return now - timedelta(days=days)
    # fallback: treat as minutes
    minutes = int(w)
    return now - timedelta(minutes=minutes)


@router.get("/summary", response_model=PriceSummary)
def get_price_summary(
    asset: str = Query(..., min_length=2, max_length=20),
    window: str = Query("24h", description="e.g., 24h, 1h, 7d or minutes"),
    db: Session = Depends(get_session),
) -> PriceSummary:
    symbol = asset.upper()
    asset_row = db.execute(
        select(Asset).where(Asset.symbol == symbol)
    ).scalar_one_or_none()
    if asset_row is None:
        raise HTTPException(status_code=404, detail="asset not found")

    try:
        cutoff = _parse_window_to_cutoff(window)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid window")
    rows = (
        db.execute(
            select(PriceHistory)
            .where(PriceHistory.asset_id == asset_row.id)
            .where(PriceHistory.ts >= cutoff)
            .order_by(PriceHistory.ts)
        )
        .scalars()
        .all()
    )
    if not rows:
        return PriceSummary(points=0, first=None, last=None, min=None, max=None, avg=None)
    prices = [float(r.price) for r in rows]
    first = prices[0]
    last = prices[-1]
    mn = min(prices)
    mx = max(prices)
    avg = sum(prices) / len(prices)
    return PriceSummary(points=len(prices), first=first, last=last, min=mn, max=mx, avg=avg)
