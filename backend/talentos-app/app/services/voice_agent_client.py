"""Thin HTTP client for calling voice-agent-service (AI outbound phone screens). This is the
ONLY place this service talks to voice-agent-service on its own behalf - the frontend also talks
to voice-agent-service directly, but only for the one read-only GET /call-agents call used to
populate a dropdown (see frontend src/api/voiceAgentDirect.ts); every call-placing/status/
transcript operation goes through this client instead, authenticated with this service's own
IAM-issued, resource-bound Service Principal credential (VOICE_AGENT_CLIENT_ID/_SECRET) rather
than the recruiter's own bearer token.

Mirrors app/services/agent_client.py's exchange-then-invoke pattern exactly, reusing the same
`agent_token_cache` from app.core.iam_client (it's keyed by client_id, so one cache instance is
shared across every machine credential this service holds).
"""
import logging
from typing import Any
from uuid import UUID

import httpx

from app.config import get_settings
from app.core.exceptions import AppException
from app.core.iam_client import agent_token_cache

logger = logging.getLogger("app.services.voice_agent_client")


class VoiceAgentServiceError(AppException):
    """Raised when voice-agent-service can't be reached or returns an unexpected error."""

    status_code = 502


async def _get_token() -> str:
    settings = get_settings()
    if not settings.VOICE_AGENT_CLIENT_ID or not settings.VOICE_AGENT_CLIENT_SECRET:
        raise VoiceAgentServiceError(
            "No IAM service principal credentials configured for voice-agent-service - set "
            "VOICE_AGENT_CLIENT_ID / VOICE_AGENT_CLIENT_SECRET in .env (see .env.example; run "
            "scripts/bootstrap_voice_agent_identity.py to mint them)."
        )
    try:
        return await agent_token_cache.get_token(settings.VOICE_AGENT_CLIENT_ID, settings.VOICE_AGENT_CLIENT_SECRET)
    except httpx.HTTPError as exc:
        logger.error("Failed to obtain an iam-service access token for voice-agent-service: %s", exc)
        raise VoiceAgentServiceError(f"Could not authenticate with iam-service: {exc}") from exc


async def _request(method: str, path: str, *, json: dict | None = None, params: dict | None = None) -> httpx.Response:
    settings = get_settings()
    token = await _get_token()
    url = f"{settings.VOICE_AGENT_SERVICE_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method, url, json=json, params=params, headers={"Authorization": f"Bearer {token}"}
            )
    except httpx.RequestError as exc:
        logger.error("Failed to reach voice-agent-service at %s: %s", url, exc)
        raise VoiceAgentServiceError(f"Could not reach voice-agent-service: {exc}") from exc

    if response.status_code >= 400:
        logger.error("voice-agent-service returned %s for %s %s: %s", response.status_code, method, path, response.text)
        raise VoiceAgentServiceError(f"voice-agent-service request failed ({response.status_code}): {response.text}")
    return response


async def list_call_agents() -> list[dict[str, Any]]:
    """Not currently called from any endpoint - the frontend hits voice-agent-service's
    GET /call-agents directly with the user's own bearer token (see
    frontend src/api/voiceAgentDirect.ts) to populate its dropdown; this exists for
    completeness/parity with the rest of this client. voice-agent-service's real response is
    `{"items": [...]}` (confirmed against its live /openapi.json), not a bare list as the fixed
    contract this was built against first described - unwrapped defensively here either way."""
    response = await _request("GET", "/call-agents")
    data = response.json()
    return data.get("items", data) if isinstance(data, dict) else data


async def create_call(
    call_agent_config_id: str, to_number: str, webhook_url: str | None = None, metadata: dict | None = None
) -> dict[str, Any]:
    payload: dict[str, Any] = {"call_agent_config_id": call_agent_config_id, "to_number": to_number}
    if webhook_url:
        payload["webhook_url"] = webhook_url
    if metadata:
        payload["metadata"] = metadata
    response = await _request("POST", "/calls", json=payload)
    return response.json()


async def get_call(voice_agent_call_id: str | UUID) -> dict[str, Any]:
    response = await _request("GET", f"/calls/{voice_agent_call_id}")
    return response.json()


async def get_conversation(voice_agent_call_id: str | UUID) -> list[dict[str, Any]]:
    response = await _request("GET", f"/calls/{voice_agent_call_id}/conversation")
    return response.json()


async def get_summary(voice_agent_call_id: str | UUID) -> dict[str, Any] | None:
    response = await _request("GET", f"/calls/{voice_agent_call_id}/summary")
    data = response.json()
    return data or None


async def cancel_call(voice_agent_call_id: str | UUID, graceful: bool = True) -> dict[str, Any]:
    response = await _request("POST", f"/calls/{voice_agent_call_id}/cancel", json={"graceful": graceful})
    return response.json()
