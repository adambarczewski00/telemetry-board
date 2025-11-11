from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def _default_db_url() -> str:
    # Default to a local SQLite database for dev/tests when DATABASE_URL is unset.
    return os.getenv("DATABASE_URL", "sqlite:///./dev.db")


ENGINE = create_engine(_default_db_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False, future=True)


def get_session() -> Generator[Session, None, None]:
    """Yield a database session; FastAPI can use this as a dependency.

    Closes the session after use to avoid connection leaks.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

