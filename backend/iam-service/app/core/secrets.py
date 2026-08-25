"""Service-principal client secrets and password-reset tokens: generated once, shown/sent
once, stored only as a SHA-256 hash - the same one-time-reveal pattern agent-builder-service
uses for its agent API keys (see agent-builder-service/app/services/api_keys.py)."""
import hashlib
import secrets

CLIENT_ID_PREFIX = "spid_"
CLIENT_SECRET_PREFIX = "spsec_"
RESET_TOKEN_PREFIX = "prt_"


def generate_client_id() -> str:
    return f"{CLIENT_ID_PREFIX}{secrets.token_urlsafe(16)}"


def generate_client_secret() -> str:
    return f"{CLIENT_SECRET_PREFIX}{secrets.token_urlsafe(32)}"


def generate_reset_token() -> str:
    return f"{RESET_TOKEN_PREFIX}{secrets.token_urlsafe(32)}"


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def mask_preview(value: str, prefix: str) -> str:
    """e.g. 'spid_Ab3d...wXyz' for display in list views - never the full value."""
    tail = value[-4:] if len(value) >= 4 else value
    return f"{prefix}...{tail}"
