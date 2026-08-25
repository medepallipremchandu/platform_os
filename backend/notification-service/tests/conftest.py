"""Test setup: a dedicated local Postgres database (talentos_notifications_test, same
server/creds as talentos_notifications - see .env), wired in via environment variables *before*
app.config.get_settings() is ever called (it's @lru_cache'd), so importing app.* in any test
module picks up the test configuration.

Celery runs eager here: `task_always_eager` makes .delay()/send_task() execute inline in the
test process, so the two-tier dispatch path is exercised for real without standing up a broker
or a worker.
"""
import os
import sys
import uuid
from pathlib import Path

import psycopg2
from cryptography.fernet import Fernet
from psycopg2 import errors as pg_errors

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

_BASE_DATABASE_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432"
_TEST_DB_NAME = "talentos_notifications_test"

os.environ["DATABASE_URL"] = f"{_BASE_DATABASE_URL}/{_TEST_DB_NAME}"
os.environ["NOTIFICATIONS_BROKER_URL"] = f"sqla+postgresql://postgres:postgres@localhost:5432/{_TEST_DB_NAME}"
os.environ["PROVIDER_SECRET_KEY"] = Fernet.generate_key().decode()
# Empty SMTP_HOST is the point of most of these tests: it is what makes the platform default
# resolve to the console sink, exactly as it does in the sandbox.
os.environ["SMTP_HOST"] = ""
os.environ["NOTIFICATIONS_MAX_RETRIES"] = "2"
os.environ["NOTIFICATIONS_RETRY_BACKOFF_SECONDS"] = "0"


def _ensure_test_database() -> None:
    conn = psycopg2.connect(f"{_BASE_DATABASE_URL.replace('postgresql+psycopg2', 'postgresql')}/postgres")
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            try:
                cur.execute(f"CREATE DATABASE {_TEST_DB_NAME}")
            except pg_errors.DuplicateDatabase:
                pass
    finally:
        conn.close()


_ensure_test_database()

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.celery_app import celery_app  # noqa: E402
from app.core_iam import CurrentActor, current_actor  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import EmailLog, NotificationProviderConfig  # noqa: E402,F401

Base.metadata.create_all(engine)

celery_app.conf.task_always_eager = True
celery_app.conf.task_eager_propagates = False


@pytest.fixture(autouse=True)
def _clean_tables():
    yield
    db = SessionLocal()
    try:
        for table in ("email_logs", "notification_provider_configs"):
            db.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
        db.commit()
    finally:
        db.close()


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def org_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def as_actor():
    """Override the token dependency instead of minting real RS256 tokens: what these tests are
    about is the authorization RULE (org scoping, superadmin bypass), and iam-service already has
    its own tests for issuing and validating the token that rule reads."""

    def _apply(*, org_id=None, permissions=(), is_superadmin=False):
        actor = CurrentActor(
            principal_type="user",
            id=str(uuid.uuid4()),
            org_id=org_id,
            permissions=list(permissions),
            is_superadmin=is_superadmin,
            email_or_name="tester@example.com",
        )
        app.dependency_overrides[current_actor] = lambda: actor
        return actor

    yield _apply
    app.dependency_overrides.clear()
