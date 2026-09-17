"""SQLAlchemy engine and session lifecycle for Phase 2.

Author: Karthikeya
Architectural layer: persistence infrastructure.
"""

from collections.abc import Generator
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.core.config import get_settings


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp for persistence fields."""

    return datetime.now(timezone.utc)


def database_url() -> str:
    """Return the configured database URL, defaulting to a local SQLite file."""

    return getattr(get_settings(), "database_url", "sqlite:///./revenuerescue.db")


_engine_kwargs = (
    {"connect_args": {"check_same_thread": False}} if database_url().startswith("sqlite") else {}
)
engine = create_engine(database_url(), future=True, pool_pre_ping=True, **_engine_kwargs)


if database_url().startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        """Make SQLite enforce the same foreign-key invariants as production DBs."""

        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


class UUIDPrimaryKeyMixin:
    """Common UUID primary key for durable domain entities."""

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)


class TimestampMixin:
    """Common UTC creation and update timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


def get_db() -> Generator:
    """Yield a session, roll back failed requests, and always close it."""

    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
