"""Encrypts telephony provider credentials at rest, so they aren't stored as plaintext in the
database. Uses a single Fernet key from settings.CREDENTIAL_ENCRYPTION_KEY - rotate by
re-encrypting all TelephonyProviderConfig rows if it ever changes (out of scope for this MVP).
Mirrors the reference implementation's app/core/crypto.py and agent-builder-service's
app/services/crypto.py.
"""
import json
from functools import lru_cache

from cryptography.fernet import Fernet

from app.config import get_settings


@lru_cache
def _fernet() -> Fernet:
    return Fernet(get_settings().CREDENTIAL_ENCRYPTION_KEY.encode())


def encrypt_credentials(payload: dict) -> str:
    raw = json.dumps(payload).encode()
    return _fernet().encrypt(raw).decode()


def decrypt_credentials(encrypted_payload: str) -> dict:
    raw = _fernet().decrypt(encrypted_payload.encode())
    return json.loads(raw)
