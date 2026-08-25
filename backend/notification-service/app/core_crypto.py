"""Fernet envelope for tenant provider secrets at rest (SMTP passwords, SendGrid API keys,
broker DSNs with embedded credentials).

Symmetric, not hashed, because unlike a password these values have to be *used* again: the
worker must recover the plaintext to authenticate to the tenant's SMTP server or broker. The
protection this buys is that a database dump alone does not hand over tenant credentials - the
key lives in PROVIDER_SECRET_KEY (.env), outside the database.
"""
import json

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class SecretsUnavailableError(RuntimeError):
    """PROVIDER_SECRET_KEY is unset or malformed. Raised at the point of use rather than at
    import time so the service still starts (and its health endpoint still answers) in a
    checkout where no key has been generated yet - only the paths that actually touch tenant
    secrets fail, and they fail loudly."""


def _fernet() -> Fernet:
    key = get_settings().PROVIDER_SECRET_KEY.strip()
    if not key:
        raise SecretsUnavailableError(
            "PROVIDER_SECRET_KEY is not set - cannot read or write tenant provider secrets. "
            'Generate one with: python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        )
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        raise SecretsUnavailableError(f"PROVIDER_SECRET_KEY is not a valid Fernet key: {exc}") from exc


def encrypt_secrets(secrets: dict) -> str | None:
    """Returns None for an empty mapping so a provider with no secret fields (e.g. a broker on a
    trusted network) leaves secrets_encrypted NULL rather than storing an encrypted '{}'."""
    if not secrets:
        return None
    return _fernet().encrypt(json.dumps(secrets).encode()).decode()


def decrypt_secrets(blob: str | None) -> dict:
    if not blob:
        return {}
    try:
        return json.loads(_fernet().decrypt(blob.encode()).decode())
    except InvalidToken as exc:
        raise SecretsUnavailableError(
            "Stored provider secrets could not be decrypted - PROVIDER_SECRET_KEY has changed "
            "since they were written. Re-enter the provider's credentials."
        ) from exc
