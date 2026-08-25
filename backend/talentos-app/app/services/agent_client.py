"""Thin HTTP client for calling agent-builder-service. This is the ONLY way this service ever
talks to an LLM - there is no model/provider/prompt code here anymore. Each AI task (JD
analysis, resume analysis, matching, question generation per type, descriptive grading) is
one published agent, identified by its own IAM-issued, resource-bound Service Principal
credential (client_id/client_secret) instead of a static agtk_... key.
"""
import logging
from typing import Any

import httpx

from app.config import get_settings
from app.core.exceptions import LLMProviderError
from app.core.iam_client import agent_token_cache

logger = logging.getLogger("app.services.agent_client")


async def invoke(agent_name: str, variables: dict[str, str]) -> Any:
    """`agent_name` is the settings prefix for one agent's credential pair, e.g.
    "JD_ANALYSIS_AGENT" reads JD_ANALYSIS_AGENT_CLIENT_ID / JD_ANALYSIS_AGENT_CLIENT_SECRET
    from .env. Exchanges that pair for a cached access token via iam-service, then calls
    agent-builder-service's /invoke with it as a Bearer token.

    Returns the agent's parsed output (dict/list if the model produced valid JSON, otherwise
    the raw string)."""
    settings = get_settings()
    client_id = getattr(settings, f"{agent_name}_CLIENT_ID", "")
    client_secret = getattr(settings, f"{agent_name}_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise LLMProviderError(
            f"No IAM service principal credentials configured for {agent_name} - set "
            f"{agent_name}_CLIENT_ID / {agent_name}_CLIENT_SECRET in .env (see .env.example)"
        )

    try:
        token = await agent_token_cache.get_token(client_id, client_secret)
    except httpx.HTTPError as exc:
        logger.error("Failed to obtain an iam-service access token for %s: %s", agent_name, exc)
        raise LLMProviderError(f"Could not authenticate with iam-service for {agent_name}: {exc}") from exc

    url = f"{settings.AGENT_BUILDER_SERVICE_URL}/invoke"
    try:
        async with httpx.AsyncClient(timeout=settings.AGENT_INVOKE_TIMEOUT_SECONDS) as client:
            response = await client.post(
                url, json={"variables": variables}, headers={"Authorization": f"Bearer {token}"}
            )
    except httpx.RequestError as exc:
        logger.error("Failed to reach agent-builder-service at %s: %s", url, exc)
        raise LLMProviderError(f"Could not reach agent-builder-service: {exc}") from exc

    if response.status_code != 200:
        logger.error("agent-builder-service returned %s: %s", response.status_code, response.text)
        raise LLMProviderError(f"Agent invocation failed ({response.status_code}): {response.text}")

    return response.json()["output"]
