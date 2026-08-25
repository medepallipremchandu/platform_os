from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

# Plain SQLAlchemy engine for this service's own tables (EmailLog, NotificationProviderConfig).
# This is a SEPARATE engine/connection pool from the one Kombu opens internally for the Celery
# broker (see app/celery_app.py) - both point at the same talentos_notifications database, but
# Kombu's SQLAlchemy transport manages its own engine from NOTIFICATIONS_BROKER_URL and knows nothing
# about this one, and vice versa. Simpler and safer than trying to share a single engine across
# two libraries that each assume they own it.
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db_session() -> Session:
    """Plain session factory for use inside Celery tasks, which have no FastAPI DI to hang a
    dependency off. Callers own closing it (every task does so in a finally block)."""
    return SessionLocal()


def get_db() -> Iterator[Session]:
    """FastAPI dependency for the provider-configuration API."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
