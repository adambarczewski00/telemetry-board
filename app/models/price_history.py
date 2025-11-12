from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Numeric, UniqueConstraint, DateTime
from sqlalchemy.types import TypeDecorator, TypeEngine
from sqlalchemy.engine import Dialect
from datetime import timezone as dt_timezone
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from .base import Base


class _UTCDateTime(TypeDecorator[datetime]):
    """A DateTime that always returns timezone-aware UTC datetimes.

    Ensures that even with SQLite (which lacks native TZ), loaded values
    have tzinfo=UTC to avoid naive/aware arithmetic errors in code/tests.
    """

    impl = DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[datetime]:  # type: ignore[override]
        return DateTime(timezone=True)

    def process_bind_param(
        self, value: datetime | None, dialect: Dialect
    ) -> object | None:  # type: ignore[override]
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=dt_timezone.utc)
        return value.astimezone(dt_timezone.utc)

    def process_result_value(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:  # type: ignore[override]
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=dt_timezone.utc)
        return value.astimezone(dt_timezone.utc)


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), index=True
    )
    # Store timezone-aware timestamps (UTC) and coerce to aware on read
    ts: Mapped[datetime] = mapped_column(_UTCDateTime(), index=True)
    price: Mapped[float] = mapped_column(Numeric(18, 8))

    __table_args__ = (
        UniqueConstraint("asset_id", "ts", name="uq_price_history_asset_ts"),
    )

    # define relationship to Asset lazily (string ref) to avoid circular import
    if TYPE_CHECKING:  # only for type checkers/linters
        from .asset import Asset

    asset: Mapped["Asset"] = relationship(backref="prices")
