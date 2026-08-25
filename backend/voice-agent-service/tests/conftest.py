"""Test setup: a dedicated local Postgres database (talentos_voice_agent_test, same server/creds
as talentos_voice_agent) so tests never touch real data, plus a throwaway RS256 keypair installed
directly into app.core.iam_client's JWKS cache - tests never make a real network call to
iam-service; they mint their own tokens signed with this test key and mimic what a validated
CurrentActor looks like. Ported from talentos-app/tests/conftest.py, which established this
exact pattern for a service in this same platform.
"""
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg2
from psycopg2 import errors as pg_errors

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

_BASE_DATABASE_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432"
_TEST_DB_NAME = "talentos_voice_agent_test"

os.environ["DATABASE_URL"] = f"{_BASE_DATABASE_URL}/{_TEST_DB_NAME}"
os.environ.setdefault("IAM_SERVICE_URL", "http://iam-service.invalid")  # never actually dialed in tests
os.environ.setdefault("IAM_JWKS_CACHE_TTL_SECONDS", "300")
os.environ.setdefault("BASE_URL", "https://voice-agent.invalid")
os.environ.setdefault("CREDENTIAL_ENCRYPTION_KEY", "vJb9YV8kQmT3Zr1cH0sXwF6nE4pL2aG7uD5oI9tK3yQ=")


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

import jwt  # noqa: E402
import pytest  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

import app.core.iam_client as iam_client  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
import app.models  # noqa: E402,F401 - registers all tables on Base.metadata
from main import app as fastapi_app  # noqa: E402

Base.metadata.create_all(engine)

TEST_KID = "test-key-1"
_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PUBLIC_KEY = _PRIVATE_KEY.public_key()

_DATA_TABLES = [
    "idempotency_keys",
    "call_summaries",
    "conversation_turns",
    "call_events",
    "calls",
    "call_agent_config_grants",
    "call_agent_configs",
    "telephony_provider_config_grants",
    "telephony_provider_configs",
]


@pytest.fixture(autouse=True)
def _install_test_jwks():
    """Bypasses the real JWKS network fetch entirely - installs the test public key directly
    into iam_client's module-level cache so current_actor() can validate tokens signed with
    _PRIVATE_KEY without ever calling httpx."""
    with iam_client._jwks_lock:
        iam_client._jwks_keys.clear()
        iam_client._jwks_keys[TEST_KID] = _PUBLIC_KEY
    iam_client._jwks_fetched_at = time.monotonic()
    yield


@pytest.fixture(autouse=True)
def _clean_tables():
    yield
    db = SessionLocal()
    try:
        for table in _DATA_TABLES:
            db.execute(text(f'DELETE FROM "{table}"'))
        db.commit()
    finally:
        db.close()


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    return TestClient(fastapi_app)


def make_token(
    *,
    org_id,
    permissions: list[str],
    principal_type: str = "user",
    email: str | None = "tester@example.com",
    name: str | None = None,
    sub: str | None = None,
    expired: bool = False,
    kid: str = TEST_KID,
) -> str:
    now = datetime.now(timezone.utc)
    exp = now - timedelta(minutes=1) if expired else now + timedelta(minutes=15)
    claims = {
        "sub": sub or str(uuid.uuid4()),
        "principal_type": principal_type,
        "org_id": str(org_id) if org_id is not None else None,
        "permissions": permissions,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": str(uuid.uuid4()),
    }
    if email is not None:
        claims["email"] = email
    if name is not None:
        claims["name"] = name
    return jwt.encode(claims, _PRIVATE_KEY, algorithm="RS256", headers={"kid": kid})


def auth_headers(**kwargs) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(**kwargs)}"}
