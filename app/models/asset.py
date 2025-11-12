from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(100), default=None)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    # Optional per-asset alert configuration (overrides global ENV when set)
    alert_pct: Mapped[float | None] = mapped_column(Numeric(9, 4), default=None)
    alert_window_min: Mapped[int | None] = mapped_column(default=None)

    # relationships defined in related models to avoid import cycles
