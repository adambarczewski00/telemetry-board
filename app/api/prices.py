from __future__ import annotations

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Asset, PriceHistory


class PricePoint(BaseModel):
    ts: datetime
    price: float

    class Config:
        from_attributes = True


router = APIRouter(prefix="/prices", tags=["prices"])


@router.get("/", response_model=List[PricePoint])
def get_prices(
    asset: str = Query(..., min_length=2, max_length=20),
    window: str | None = Query(None),
    db: Session = Depends(get_session),
) -> List[PricePoint]:
    symbol = asset.upper()
    asset_row = db.execute(select(Asset).where(Asset.symbol == symbol)).scalar_one_or_none()
    if asset_row is None:
        raise HTTPException(status_code=404, detail="asset not found")

    # MVP: ignore window and just return existing points (if any). May be empty.
    rows = (
        db.execute(
            select(PriceHistory).where(PriceHistory.asset_id == asset_row.id).order_by(PriceHistory.ts)
        )
        .scalars()
        .all()
    )
    return [PricePoint.model_validate(r) for r in rows]

