"""notification-service as a relying party on iam-service's RS256 access tokens.

Same posture as agent-builder-service and voice-agent-service: tokens are validated locally
against iam-service's published JWKS, cached by `kid`, so no synchronous call to iam-service
sits on the request path. Only the provider-configuration API needs this - the Celery worker
authenticates nothing, because a task is only ever produced by a service that already
authorized its caller.
"""
import logging
import threading
import time
import uuid
from dataclasses import dataclass

import httpx
import jwt
from fastapi import Depends, Header, HTTPException, status

from app.config import get_settings

logger = logging.getLogger("app.core_iam")

ALGORITHM = "RS256"

_jwks_by_kid: dict[str, dict] = {}
_jwks_fetched_at: float = 0.0
_jwks_lock = threading.Lock()


def _fetch_jwks() -> dict[str, dict]:
    response = httpx.get(get_settings().IAM_JWKS_URL, timeout=5.0)
    response.raise_for_status()
    return {key["kid"]: key for key in response.json().get("keys", []) if "kid" in key}


def _refresh_jwks() -> dict[str, dict]:
    global _jwks_by_kid, _jwks_fetched_at
    fetched = _fetch_jwks()
    with _jwks_lock:
        _jwks_by_kid = fetched
        _jwks_fetched_at = time.monotonic()
    return fetched


def _public_key_for(kid: str | None):
    settings = get_settings()
    with _jwks_lock:
        cache = dict(_jwks_by_kid)
        age = time.monotonic() - _jwks_fetched_at if _jwks_fetched_at else None

    if not cache:
        cache = _refresh_jwks()
    elif age is not None and age > settings.IAM_JWKS_CACHE_SECONDS:
        try:
            cache = _refresh_jwks()
        except Exception:
            logger.warning("JWKS refresh failed - serving the stale cache", exc_info=True)

    if kid is not None and kid not in cache:
        # A kid miss usually means iam-service rotated its signing key since the last fetch.
        try:
            cache = _refresh_jwks()
        except Exception:
            logger.warning("JWKS refresh on kid miss failed", exc_info=True)

    jwk = cache.get(kid) if kid is not None else None
    return jwt.algorithms.RSAAlgorithm.from_jwk(jwk) if jwk is not None else None


def decode_access_token(token: str) -> dict:
    header = jwt.get_unverified_header(token)
    public_key = _public_key_for(header.get("kid"))
    if public_key is None:
        raise jwt.InvalidKeyError(f"Unknown signing key id: {header.get('kid')!r}")
    return jwt.decode(token, public_key, algorithms=[ALGORITHM])


@dataclass
class CurrentActor:
    principal_type: str
    id: str
    org_id: uuid.UUID | None
    permissions: list[str]
    is_superadmin: bool
    email_or_name: str


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid Authorization header")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid Authorization header")
    return token


def current_actor(authorization: str | None = Header(default=None)) -> CurrentActor:
    token = _extract_bearer_token(authorization)
    try:
        claims = decode_access_token(token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    raw_org = claims.get("org_id")
    try:
        org_id = uuid.UUID(raw_org) if raw_org else None
    except ValueError:
        org_id = None

    return CurrentActor(
        principal_type=claims.get("principal_type", ""),
        id=claims.get("sub", ""),
        org_id=org_id,
        permissions=claims.get("permissions") or [],
        # A platform superadmin carries no org membership and therefore no org-scoped
        # permissions, so this boolean - not the permission list - is what lets them administer
        # any tenant's providers. It is deliberately a separate axis: holding every
        # talentos.* permission still does not make a principal a superadmin.
        is_superadmin=bool(claims.get("is_superadmin")),
        email_or_name=claims.get("email") or claims.get("name") or claims.get("sub", ""),
    )


def require_org_permission(*codes: str):
    """Authorizes a request against a specific organization named in the path.

    A superadmin passes for any organization. Everyone else must both hold at least one of the
    permissions AND be acting inside that organization - a token scoped to org A must never be
    able to read or rewrite org B's mail credentials, no matter what permissions it carries.

    Any-of rather than all-of, because read endpoints accept either the read or the manage
    permission: an admin who can rewrite a provider being unable to look at it would be a
    footgun, not a security boundary."""

    def _dependency(organization_id: uuid.UUID, actor: CurrentActor = Depends(current_actor)) -> CurrentActor:
        if actor.is_superadmin:
            return actor
        if not any(code in actor.permissions for code in codes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=f"Missing permission: {' or '.join(codes)}"
            )
        if actor.org_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Token is not scoped to the requested organization",
            )
        return actor

    return _dependency


__all__ = ["CurrentActor", "current_actor", "require_org_permission", "decode_access_token"]
