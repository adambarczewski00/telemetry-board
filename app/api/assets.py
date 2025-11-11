from __future__ import annotations

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Asset


class AssetCreate(BaseModel):
    symbol: str = Field(..., min_length=2, max_length=20)
    name: str | None = Field(default=None, max_length=100)

    def normalized(self) -> "AssetCreate":
        return AssetCreate(symbol=self.symbol.upper(), name=self.name)


class AssetOut(BaseModel):
    id: int
    symbol: str
    name: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("/", response_model=List[AssetOut])
def list_assets(db: Session = Depends(get_session)) -> List[AssetOut]:
    rows = db.execute(select(Asset).order_by(Asset.symbol)).scalars().all()
    return [AssetOut.model_validate(r) for r in rows]


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=AssetOut)
def create_asset(payload: AssetCreate, db: Session = Depends(get_session)) -> AssetOut:
    data = payload.normalized()
    asset = Asset(symbol=data.symbol, name=data.name)
    db.add(asset)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="asset already exists"
        )
    db.refresh(asset)
    return AssetOut.model_validate(asset)
