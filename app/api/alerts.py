from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Alert, Asset


class AlertOut(BaseModel):
    id: int
    asset_id: int
    triggered_at: str
    window_minutes: int
    change_pct: float

    model_config = ConfigDict(from_attributes=True)


router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/", response_model=List[AlertOut])
def get_alerts(
    asset: str = Query(..., min_length=2, max_length=20),
    limit: int = Query(20, ge=1, le=1000),
    db: Session = Depends(get_session),
) -> List[AlertOut]:
    symbol = asset.upper()
    asset_row = db.execute(
        select(Asset).where(Asset.symbol == symbol)
    ).scalar_one_or_none()
    if asset_row is None:
        raise HTTPException(status_code=404, detail="asset not found")

    rows = (
        db.execute(
            select(Alert)
            .where(Alert.asset_id == asset_row.id)
            .order_by(Alert.triggered_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return [AlertOut.model_validate(r) for r in rows]
