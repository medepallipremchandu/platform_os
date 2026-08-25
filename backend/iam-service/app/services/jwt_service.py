"""Access-token issuing/validation. RS256, signed with the private key loaded from disk,
kid taken from Settings.JWT_KEY_ID so a future key rotation just adds a second JWK to the
published set without invalidating tokens signed under the old kid.

Claims (see design doc §5, and the "identity claim" follow-up from the platform team):
    sub             user id or service_principal id (str(UUID))
    principal_type  "user" | "service_principal"
    org_id          the active organization for this token (str(UUID))
    permissions     resolved effective permission strings at issue time (flat list)
    resource_scope  {"type": ..., "id": ...} - only for a resource-bound ServicePrincipal
    email           user's email - only for principal_type == "user"
    name            service principal's name - only for principal_type == "service_principal"
    iat / exp / jti

`email`/`name` let talentos-app and agent-builder-service keep writing a plain
human-readable string into their existing created_by/changed_by audit columns without a
schema change: a consumer derives that string as
    claims.get("email") or claims.get("name") or claims["sub"]
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.config import get_settings
from app.core.jwt_keys import load_private_key, load_public_key

ALGORITHM = "RS256"


def issue_access_token(
    *,
    sub: uuid.UUID,
    principal_type: str,
    org_id: uuid.UUID | None,
    permissions: list[str],
    resource_scope: dict | None = None,
    email: str | None = None,
    name: str | None = None,
) -> tuple[str, dict]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    jti = str(uuid.uuid4())

    claims: dict[str, Any] = {
        "sub": str(sub),
        "principal_type": principal_type,
        "org_id": str(org_id) if org_id is not None else None,
        "permissions": permissions,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": jti,
    }
    if resource_scope is not None:
        claims["resource_scope"] = resource_scope
    if principal_type == "user" and email is not None:
        claims["email"] = email
    if principal_type == "service_principal" and name is not None:
        claims["name"] = name

    token = jwt.encode(
        claims,
        load_private_key(),
        algorithm=ALGORITHM,
        headers={"kid": settings.JWT_KEY_ID},
    )
    return token, claims


def decode_access_token(token: str) -> dict:
    """Raises jwt.PyJWTError subclasses on any invalid/expired/malformed token."""
    return jwt.decode(token, load_public_key(), algorithms=[ALGORITHM])


def access_token_ttl_seconds() -> int:
    return get_settings().ACCESS_TOKEN_EXPIRE_MINUTES * 60
