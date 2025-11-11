from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from .base import Base


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    ts: Mapped[datetime] = mapped_column(index=True)
    price: Mapped[float] = mapped_column(Numeric(18, 8))

    __table_args__ = (
        UniqueConstraint("asset_id", "ts", name="uq_price_history_asset_ts"),
    )

    # define relationship to Asset lazily (string ref) to avoid circular import
    if TYPE_CHECKING:  # only for type checkers/linters
        from .asset import Asset

    asset: Mapped["Asset"] = relationship(backref="prices")
