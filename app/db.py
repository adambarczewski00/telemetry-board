from __future__ import annotations

import os
from typing import Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base


_engine: Optional[Engine] = None
_engine_url: Optional[str] = None


def _default_db_url() -> str:
    # Default to a local SQLite database for dev/tests when DATABASE_URL is unset.
    return os.getenv("DATABASE_URL", "sqlite:///./dev.db")


def get_engine() -> Engine:
    """Return a process-wide Engine, recreating it when DATABASE_URL changes.

    This makes tests reliable when they override DATABASE_URL per test.
    """
    global _engine, _engine_url
    current_url = _default_db_url()
    if _engine is None or _engine_url != current_url:
        _engine = create_engine(current_url, pool_pre_ping=True)
        _engine_url = current_url
    return _engine


def get_session() -> Generator[Session, None, None]:
    """Yield a database session; FastAPI can use this as a dependency.

    Closes the session after use to avoid connection leaks.
    """
    SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all() -> None:
    """Create all tables using SQLAlchemy metadata (useful for tests/dev)."""
    Base.metadata.create_all(bind=get_engine())
