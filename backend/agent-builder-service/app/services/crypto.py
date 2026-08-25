"""Encrypts provider credentials (model API keys) at rest, so they aren't stored as plaintext
in the database. Uses a single Fernet key from settings.ENCRYPTION_KEY - rotate by
re-encrypting all Model rows if it ever changes (out of scope for this MVP)."""
from functools import lru_cache

from cryptography.fernet import Fernet

from app.config import get_settings


@lru_cache
def _fernet() -> Fernet:
    return Fernet(get_settings().ENCRYPTION_KEY.encode())


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()
