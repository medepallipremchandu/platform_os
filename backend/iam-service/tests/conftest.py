"""Test setup: a dedicated local Postgres database (talentos_iam_test, same server/creds as
talentos_iam - see .env) and a throwaway RSA keypair, both wired in via environment variables
*before* app.config.get_settings() is ever called (it's @lru_cache'd), so importing app.* in
any test module picks up the test configuration.
"""
import os
import sys
import tempfile
import uuid
from pathlib import Path

import psycopg2
from psycopg2 import errors as pg_errors

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

_TMP_DIR = Path(tempfile.mkdtemp(prefix="iam_test_keys_"))
_BASE_DATABASE_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432"
_TEST_DB_NAME = "talentos_iam_test"

os.environ.setdefault("DATABASE_URL", f"{_BASE_DATABASE_URL}/{_TEST_DB_NAME}")
os.environ.setdefault("JWT_PRIVATE_KEY_PATH", str(_TMP_DIR / "private.pem"))
os.environ.setdefault("JWT_PUBLIC_KEY_PATH", str(_TMP_DIR / "public.pem"))
os.environ.setdefault("JWT_KEY_ID", "test-key-1")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "15")
os.environ.setdefault("REFRESH_TOKEN_EXPIRE_DAYS", "30")
os.environ.setdefault("LOGIN_LOCKOUT_THRESHOLD", "3")
os.environ.setdefault("LOGIN_LOCKOUT_WINDOW_MINUTES", "15")
os.environ.setdefault("LOGIN_LOCKOUT_DURATION_MINUTES", "15")
os.environ.setdefault("PASSWORD_MIN_LENGTH", "12")


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


def _generate_test_keypair() -> None:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_path = Path(os.environ["JWT_PRIVATE_KEY_PATH"])
    public_path = Path(os.environ["JWT_PUBLIC_KEY_PATH"])
    if private_path.exists() and public_path.exists():
        return
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    public_path.write_bytes(
        key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )


_ensure_test_database()
_generate_test_keypair()

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.permission import Permission  # noqa: E402
from app.models.role_definition import RoleDefinition  # noqa: E402
from app.models.role_definition_permission import RoleDefinitionPermission  # noqa: E402

sys.path.insert(0, str(BACKEND_DIR / "scripts"))
import seed_permissions_and_roles as seed_mod  # noqa: E402

Base.metadata.create_all(engine)

_DATA_TABLES = [
    "audit_log_entries",
    "password_reset_tokens",
    "revoked_token_jti",
    "refresh_tokens",
    "role_assignments",
    "organization_memberships",
    "service_principals",
    "users",
    "organizations",
]


@pytest.fixture(scope="session", autouse=True)
def _seed_catalog():
    db = SessionLocal()
    try:
        permissions_by_code = seed_mod.seed_permissions(db)
        seed_mod.seed_builtin_roles(db, permissions_by_code)
    finally:
        db.close()
    yield


@pytest.fixture(autouse=True)
def _clean_tables():
    yield
    db = SessionLocal()
    try:
        # NOTE: organizations/role_assignments participate in FKs from role_definitions and
        # role_definition_permissions (organization_id, role_definition_id), so a CASCADE
        # truncate here also wipes the seeded permission catalog and built-in roles - reseed
        # (idempotent) right after.
        for table in _DATA_TABLES:
            db.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
        db.commit()
        permissions_by_code = seed_mod.seed_permissions(db)
        seed_mod.seed_builtin_roles(db, permissions_by_code)
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
def client():
    return TestClient(app)


@pytest.fixture()
def owner_role_id(db):
    role = db.query(RoleDefinition).filter(
        RoleDefinition.organization_id.is_(None), RoleDefinition.name == "Organization Owner"
    ).one()
    return role.id


def unique_email() -> str:
    return f"user-{uuid.uuid4().hex[:10]}@example.com"
