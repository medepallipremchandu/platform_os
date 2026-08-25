"""Shared IAM validation/integration module. agent-builder-service is a relying party on
iam-service's RS256-signed access tokens - it validates them locally against iam-service's
published JWKS (no synchronous call to iam-service on the request path), exactly as described
in the IAM design doc §5/§7.

This module also exposes:
  - `get_service_token()`: this service's own machine-identity token (client-credentials
    grant against IAM_CLIENT_ID/IAM_CLIENT_SECRET from .env - see scripts/bootstrap_iam_identity.py),
    used only to call iam-service's service-principal-management endpoints when publishing or
    rotating an agent's invoke credential.
  - `post_audit_event(...)`: fire-and-forget audit event posting using the INBOUND request's
    own bearer token, so the audit entry is attributed to whoever actually made the request.
"""
import logging
import threading
import time
from dataclasses import dataclass

import httpx
import jwt
from fastapi import Depends, Header, HTTPException, status

from app.config import get_settings

logger = logging.getLogger("app.core.iam_client")

ALGORITHM = "RS256"


# --- JWKS caching -----------------------------------------------------------------------
#
# Cached by `kid`. On a `kid` miss (e.g. iam-service rotated its signing key) we force a
# refresh once before giving up. We also opportunistically refresh in the background once
# IAM_JWKS_CACHE_TTL_SECONDS has elapsed, so a long-lived process picks up a rotated key even
# without ever seeing a miss.

_jwks_by_kid: dict[str, dict] = {}
_jwks_fetched_at: float = 0.0
_jwks_lock = threading.Lock()


def _jwks_url() -> str:
    return f"{get_settings().IAM_SERVICE_URL}/.well-known/jwks.json"


def _fetch_jwks() -> dict[str, dict]:
    resp = httpx.get(_jwks_url(), timeout=5.0)
    resp.raise_for_status()
    keys = resp.json().get("keys", [])
    return {key["kid"]: key for key in keys if "kid" in key}


def _refresh_jwks() -> dict[str, dict]:
    global _jwks_by_kid, _jwks_fetched_at
    fetched = _fetch_jwks()
    with _jwks_lock:
        _jwks_by_kid = fetched
        _jwks_fetched_at = time.monotonic()
    return fetched


def _get_jwk(kid: str | None) -> dict | None:
    settings = get_settings()
    with _jwks_lock:
        cache = dict(_jwks_by_kid)
        age = time.monotonic() - _jwks_fetched_at if _jwks_fetched_at else None

    if not cache:
        cache = _refresh_jwks()
    elif age is not None and age > settings.IAM_JWKS_CACHE_TTL_SECONDS:
        # Cache is stale - refresh in the background; serve the current cache in the
        # meantime so a slow/unreachable iam-service never blocks a request that has a
        # valid, still-cached key.
        try:
            cache = _refresh_jwks()
        except Exception:
            logger.warning("Background JWKS refresh failed - serving stale cache", exc_info=True)

    if kid is not None and kid not in cache:
        # kid miss: could be a freshly rotated key we haven't seen yet - force one refresh.
        try:
            cache = _refresh_jwks()
        except Exception:
            logger.warning("JWKS refresh on kid miss failed", exc_info=True)

    return cache.get(kid) if kid is not None else None


def _public_key_for(kid: str | None):
    jwk = _get_jwk(kid)
    if jwk is None:
        return None
    return jwt.algorithms.RSAAlgorithm.from_jwk(jwk)


def decode_access_token(token: str) -> dict:
    """Raises jwt.PyJWTError subclasses on any invalid/expired/malformed/unknown-key token."""
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError:
        raise
    kid = header.get("kid")
    public_key = _public_key_for(kid)
    if public_key is None:
        raise jwt.InvalidKeyError(f"Unknown signing key id: {kid!r}")
    return jwt.decode(token, public_key, algorithms=[ALGORITHM])


# --- Current actor / permission dependencies --------------------------------------------


@dataclass
class CurrentActor:
    principal_type: str
    id: str
    org_id: str
    permissions: list[str]
    resource_scope: dict | None
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

    return CurrentActor(
        principal_type=claims.get("principal_type", ""),
        id=claims.get("sub", ""),
        org_id=claims.get("org_id") or "",
        permissions=claims.get("permissions") or [],
        resource_scope=claims.get("resource_scope"),
        email_or_name=claims.get("email") or claims.get("name") or claims.get("sub"),
    )


def require_permission(code: str):
    def _dependency(actor: CurrentActor = Depends(current_actor)) -> CurrentActor:
        if code not in actor.permissions:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Missing permission: {code}")
        return actor

    return _dependency


# --- This service's own machine identity (client-credentials grant) ----------------------


class _ServiceTokenCache:
    """Caches this service's own client-credentials access token in memory, refreshing
    ~1 minute before expiry so steady-state publish/rotate calls don't pay a token round trip
    every time."""

    _REFRESH_MARGIN_SECONDS = 60

    def __init__(self) -> None:
        self._token: str | None = None
        self._expires_at: float = 0.0
        self._lock = threading.Lock()

    def get(self) -> str:
        with self._lock:
            if self._token is not None and time.monotonic() < self._expires_at - self._REFRESH_MARGIN_SECONDS:
                return self._token
            settings = get_settings()
            if not settings.IAM_CLIENT_ID or not settings.IAM_CLIENT_SECRET:
                raise RuntimeError(
                    "IAM_CLIENT_ID/IAM_CLIENT_SECRET are not configured - run "
                    "scripts/bootstrap_iam_identity.py first."
                )
            resp = httpx.post(
                f"{settings.IAM_SERVICE_URL}/auth/token",
                json={"client_id": settings.IAM_CLIENT_ID, "client_secret": settings.IAM_CLIENT_SECRET},
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()
            self._token = data["access_token"]
            self._expires_at = time.monotonic() + data["expires_in"]
            return self._token

    def invalidate(self) -> None:
        with self._lock:
            self._token = None
            self._expires_at = 0.0


_service_token_cache = _ServiceTokenCache()


def get_service_token() -> str:
    """This service's own machine-identity access token - used only to call iam-service's
    service-principal-management endpoints (publish/regenerate an agent's invoke credential),
    never for validating or standing in for an end user's permissions."""
    return _service_token_cache.get()


# --- Audit events --------------------------------------------------------------------------


def post_audit_event(
    bearer_token: str,
    *,
    action: str,
    target_type: str,
    target_id: str | None = None,
    result: str = "success",
    changes: dict | None = None,
    correlation_id: str | None = None,
) -> None:
    """Fire-and-forget POST to iam-service's /audit/events, using the PASSED-THROUGH bearer
    token from the inbound request (not this service's own machine identity), so the audit
    entry's actor/org is correctly attributed to whoever made the original request.

    `bearer_token` is the raw `Authorization` header value (e.g. "Bearer eyJ...") as received
    on the inbound request. Failures here must never break the actual business operation.
    """
    settings = get_settings()
    payload = {
        "action": action,
        "target_type": target_type,
        "target_id": str(target_id) if target_id is not None else None,
        "result": result,
        "changes": changes,
        "correlation_id": correlation_id,
    }
    try:
        httpx.post(
            f"{settings.IAM_SERVICE_URL}/audit/events",
            json=payload,
            headers={"Authorization": bearer_token},
            timeout=5.0,
        )
    except Exception:
        logger.warning("Failed to post audit event %r for %s %s", action, target_type, target_id, exc_info=True)


__all__ = [
    "CurrentActor",
    "current_actor",
    "require_permission",
    "decode_access_token",
    "get_service_token",
    "post_audit_event",
]
