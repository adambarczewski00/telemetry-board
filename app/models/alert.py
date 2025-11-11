from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from .base import Base


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), index=True
    )
    triggered_at: Mapped[datetime] = mapped_column(index=True)
    window_minutes: Mapped[int] = mapped_column()
    change_pct: Mapped[float] = mapped_column(Numeric(9, 4))

    if TYPE_CHECKING:  # only for type checkers/linters
        from .asset import Asset

    asset: Mapped["Asset"] = relationship(backref="alerts")
