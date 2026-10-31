"""SQLAlchemy engine and session lifecycle for Phase 2.

Author: Karthikeya
Architectural layer: persistence infrastructure.
"""

from collections.abc import Generator
from datetime import datetime, timezone
import logging
from uuid import UUID, uuid4

from sqlalchemy import DateTime, create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.core.config import get_settings

logger = logging.getLogger("revenuerescue.database")


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp for persistence fields."""
    return datetime.now(timezone.utc)


def database_url() -> str:
    """Return the configured database URL, defaulting to a local SQLite file."""
    return getattr(get_settings(), "database_url", "sqlite:///./revenuerescue.db")


def create_app_engine():
    """Create a configured SQLAlchemy engine respecting the active database dialect."""
    url = database_url()
    settings = get_settings()

    if url.startswith("sqlite"):
        engine_instance = create_engine(
            url,
            future=True,
            pool_pre_ping=True,
            connect_args={"check_same_thread": False},
            echo=settings.db_echo,
        )

        @event.listens_for(engine_instance, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
            """Make SQLite enforce the same foreign-key invariants as production DBs."""
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine_instance

    # PostgreSQL configuration
    return create_engine(
        url,
        future=True,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        echo=settings.db_echo,
    )


engine = create_app_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def check_database_connection() -> tuple[bool, str]:
    """Test database connectivity with a lightweight SELECT 1 probe.

    Returns:
        tuple[bool, str]: (is_healthy, status_message)
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "connected"
    except Exception as exc:
        logger.error("Database health check probe failed: %s", exc)
        return False, "unavailable"


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
