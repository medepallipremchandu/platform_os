"""This service is a Bearer-token relying party of iam-service (design doc §7): it validates
incoming access tokens locally against iam-service's published JWKS - no synchronous call to
iam-service on the request path - and posts audit events / exchanges client-credentials tokens
via a couple of small outbound calls. Ported near-verbatim from talentos-app's
app/core/iam_client.py, which has already been through this exact migration.

Pieces:
    current_actor          FastAPI dependency: validates the inbound Bearer token, returns a
                            CurrentActor.
    require_permission     Dependency factory: 403s if the token's permissions claim doesn't
                            contain the given code.
    post_audit_event        Fire-and-forget POST to iam-service's /audit/events. For ordinary
                            (IAM-authenticated) routes this uses the inbound request's own
                            bearer token, so the audit entry's actor/org is derived server-side
                            by iam-service from that same token. The two Twilio webhook routes
                            have no inbound bearer token (Twilio, not IAM, calls them) - they use
                            this service's own machine-identity token instead (get_service_token),
                            so those audit entries are attributed to voice-agent-service itself
                            as a system actor.
    ClientCredentialsTokenCache / token_cache
                            Exchanges any client_id/client_secret pair for a short-lived access
                            token via POST /auth/token, caching it in memory until ~1 minute
                            before expiry. Used both for the 3 conversation-agent credentials
                            (app/services/conversation_client.py) and for this service's own
                            machine identity (get_service_token below).
"""
import json
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

# --- JWKS cache: keyed by kid, refreshed on a kid miss or once the TTL has elapsed. ---
_jwks_lock = threading.Lock()
_jwks_keys: dict[str, object] = {}
_jwks_fetched_at: float = 0.0


def _fetch_jwks() -> dict:
    settings = get_settings()
    url = f"{settings.IAM_SERVICE_URL}/.well-known/jwks.json"
    response = httpx.get(url, timeout=10.0)
    response.raise_for_status()
    return response.json()


def _refresh_jwks_cache() -> None:
    global _jwks_fetched_at
    data = _fetch_jwks()
    keys = {}
    for jwk in data.get("keys", []):
        kid = jwk.get("kid")
        if not kid:
            continue
        keys[kid] = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))
    with _jwks_lock:
        _jwks_keys.clear()
        _jwks_keys.update(keys)
        _jwks_fetched_at = time.monotonic()


def _get_signing_key(kid: str):
    """Returns the cached public key for `kid`, refreshing the cache on a kid miss or once
    IAM_JWKS_CACHE_TTL_SECONDS has elapsed since the last fetch."""
    settings = get_settings()
    with _jwks_lock:
        cached = _jwks_keys.get(kid)
        stale = (time.monotonic() - _jwks_fetched_at) > settings.IAM_JWKS_CACHE_TTL_SECONDS

    if cached is not None and not stale:
        return cached

    try:
        _refresh_jwks_cache()
    except httpx.HTTPError as exc:
        logger.error("Failed to fetch JWKS from iam-service: %s", exc)
        with _jwks_lock:
            cached = _jwks_keys.get(kid)
        if cached is not None:
            return cached  # serve stale key rather than fail every request during an outage
        return None

    with _jwks_lock:
        return _jwks_keys.get(kid)


def reset_jwks_cache_for_tests() -> None:
    global _jwks_fetched_at
    with _jwks_lock:
        _jwks_keys.clear()
        _jwks_fetched_at = 0.0


@dataclass
class CurrentActor:
    principal_type: str
    id: str
    org_id: str
    permissions: list[str]
    email_or_name: str
    token: str


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid Authorization header"
        )
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid Authorization header"
        )
    return token


def current_actor(authorization: str | None = Header(default=None)) -> CurrentActor:
    token = _extract_bearer_token(authorization)

    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    kid = header.get("kid")
    if not kid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token: missing kid")

    signing_key = _get_signing_key(kid)
    if signing_key is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown token signing key")

    try:
        claims = jwt.decode(token, signing_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    email_or_name = claims.get("email") or claims.get("name") or claims.get("sub")
    return CurrentActor(
        principal_type=claims.get("principal_type"),
        id=claims.get("sub"),
        org_id=claims.get("org_id"),
        permissions=claims.get("permissions") or [],
        email_or_name=email_or_name,
        token=token,
    )


def require_permission(code: str):
    def _dependency(actor: CurrentActor = Depends(current_actor)) -> CurrentActor:
        if code not in actor.permissions:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Missing permission: {code}")
        return actor

    return _dependency


async def post_audit_event(
    bearer_token: str,
    *,
    action: str,
    target_type: str,
    target_id: str | None = None,
    result: str = "success",
    changes: dict | None = None,
) -> None:
    """Fire-and-forget: posts to iam-service using the given bearer token (raw token, no
    "Bearer " prefix) so iam-service derives organization_id/actor_type/actor_id server-side
    from that same token (see iam-service/app/api/v1/audit.py). Never raises - a failure here
    must never break the caller's actual business operation."""
    settings = get_settings()
    url = f"{settings.IAM_SERVICE_URL}/audit/events"
    payload = {
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "result": result,
        "changes": changes,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(url, json=payload, headers={"Authorization": f"Bearer {bearer_token}"})
        if response.status_code >= 400:
            logger.warning(
                "iam-service rejected audit event action=%s target_type=%s: %s %s",
                action,
                target_type,
                response.status_code,
                response.text,
            )
    except Exception:
        logger.exception("Failed to post audit event action=%s target_type=%s to iam-service", action, target_type)


class ClientCredentialsTokenCache:
    """Exchanges any (client_id, client_secret) pair for an access token via iam-service's
    POST /auth/token, caching it in memory keyed by client_id until ~1 minute before its exp
    (design doc §6.2). Shared by app/services/conversation_client.py (the 3 conversation-agent
    credentials) and get_service_token below (this service's own machine identity) - one cache,
    one refresh policy."""

    _REFRESH_MARGIN_SECONDS = 60

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[str, float]] = {}  # client_id -> (token, expiry_monotonic)

    async def get_token(self, client_id: str, client_secret: str) -> str:
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(client_id)
        if cached is not None and cached[1] - now > self._REFRESH_MARGIN_SECONDS:
            return cached[0]

        token, expires_in = await self._exchange(client_id, client_secret)
        with self._lock:
            self._cache[client_id] = (token, time.monotonic() + expires_in)
        return token

    async def _exchange(self, client_id: str, client_secret: str) -> tuple[str, int]:
        settings = get_settings()
        url = f"{settings.IAM_SERVICE_URL}/auth/token"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json={"client_id": client_id, "client_secret": client_secret})
        response.raise_for_status()
        data = response.json()
        return data["access_token"], data["expires_in"]

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


token_cache = ClientCredentialsTokenCache()


async def get_service_token() -> str:
    """This service's own machine-identity access token (IAM_CLIENT_ID/IAM_CLIENT_SECRET,
    minted by scripts/bootstrap_iam_identity.py) - used only to post system-attributed audit
    events for the two Twilio webhook routes, which have no end-user bearer token of their own.
    Never used to stand in for an end user's permissions."""
    settings = get_settings()
    if not settings.IAM_CLIENT_ID or not settings.IAM_CLIENT_SECRET:
        raise RuntimeError(
            "IAM_CLIENT_ID/IAM_CLIENT_SECRET are not configured - run scripts/bootstrap_iam_identity.py first."
        )
    return await token_cache.get_token(settings.IAM_CLIENT_ID, settings.IAM_CLIENT_SECRET)


__all__ = [
    "CurrentActor",
    "current_actor",
    "require_permission",
    "post_audit_event",
    "ClientCredentialsTokenCache",
    "token_cache",
    "get_service_token",
    "reset_jwks_cache_for_tests",
]
