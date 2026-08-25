"""Replaces the reference implementation's app/providers/ai.py + app/services/conversation.py.
There is no AiProvider / per-org AI credential here at all - conversation generation is
delegated to agent-builder-service, the platform's single canonical place for AI model +
prompt-template + agent management. Three published agents (Consent Turn, Main Conversation
Turn, Summary - see scripts/seed_call_agents.py) stand in for the reference repo's
consent_turn/main_turn/generate_summary methods.

Each of the 3 agents is invoked with its own resource-bound IAM Service Principal credential
(CONSENT_TURN_AGENT_CLIENT_ID/_SECRET etc. in .env), exchanged for a cached access token via
iam-service's /auth/token (app.core.iam_client.token_cache) exactly like talentos-app's
app/services/agent_client.py does for its own agents.

agent-builder-service's /invoke only accepts dict[str, str] variables (its templating is plain
{{name}} substitution, no logic) - so any structured value (the conversation history so far, the
extracted-fields spec) is JSON-stringified here before being passed, the same "flatten to a
string in Python before invoking" convention talentos-app's services use for their own
list-to-string flattening.
"""
from __future__ import annotations

import json
import logging

import httpx

from app.config import get_settings
from app.core.exceptions import ConversationAgentError
from app.core.iam_client import token_cache

logger = logging.getLogger("app.services.conversation_client")

_NO_TIME_NOTICE = "No time notice needed for this turn."


async def _invoke(agent_name: str, variables: dict[str, str]) -> dict:
    """`agent_name` is the settings prefix for one agent's credential pair, e.g.
    "CONSENT_TURN_AGENT" reads CONSENT_TURN_AGENT_CLIENT_ID / CONSENT_TURN_AGENT_CLIENT_SECRET
    from .env. Exchanges that pair for a cached access token via iam-service, then calls
    agent-builder-service's /invoke with it as a Bearer token. Returns the agent's parsed JSON
    output as a dict - raises ConversationAgentError for anything else (missing credentials,
    network failure, non-2xx, or output that isn't a JSON object)."""
    settings = get_settings()
    client_id = getattr(settings, f"{agent_name}_CLIENT_ID", "")
    client_secret = getattr(settings, f"{agent_name}_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise ConversationAgentError(
            f"No IAM service principal credentials configured for {agent_name} - set "
            f"{agent_name}_CLIENT_ID / {agent_name}_CLIENT_SECRET in .env (see .env.example). "
            f"Run scripts/seed_call_agents.py against a running agent-builder-service first."
        )

    try:
        token = await token_cache.get_token(client_id, client_secret)
    except httpx.HTTPError as exc:
        logger.error("Failed to obtain an iam-service access token for %s: %s", agent_name, exc)
        raise ConversationAgentError(f"Could not authenticate with iam-service for {agent_name}: {exc}") from exc

    url = f"{settings.AGENT_BUILDER_SERVICE_URL}/invoke"
    try:
        async with httpx.AsyncClient(timeout=settings.AGENT_INVOKE_TIMEOUT_SECONDS) as client:
            response = await client.post(
                url, json={"variables": variables}, headers={"Authorization": f"Bearer {token}"}
            )
    except httpx.RequestError as exc:
        logger.error("Failed to reach agent-builder-service at %s: %s", url, exc)
        raise ConversationAgentError(f"Could not reach agent-builder-service: {exc}") from exc

    if response.status_code != 200:
        logger.error("agent-builder-service returned %s: %s", response.status_code, response.text)
        raise ConversationAgentError(f"Agent invocation failed ({response.status_code}): {response.text}")

    output = response.json()["output"]
    if isinstance(output, dict):
        return output
    if isinstance(output, str):
        try:
            parsed = json.loads(output)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            return parsed
    raise ConversationAgentError(f"{agent_name} did not return a JSON object: {output!r}")


def _field_spec(fields: list[dict]) -> str:
    return json.dumps({f["name"]: {"type": f["type"], "description": f["description"]} for f in fields})


async def consent_turn(*, persona: str, consent_line: str, callee_speech: str) -> dict:
    """Returns {"consent": "yes"|"no"|"unclear", "ai_response": str}."""
    return await _invoke(
        "CONSENT_TURN_AGENT",
        {"persona": persona, "consent_line": consent_line, "callee_reply": callee_speech},
    )


async def main_turn(
    *,
    persona: str,
    objective: str,
    fields: list[dict],
    closing_line: str,
    history: list[dict],
    callee_speech: str,
    time_notice: str | None = None,
) -> dict:
    """Returns {"ai_response": str, "fields": {...}, "done": bool}."""
    return await _invoke(
        "MAIN_TURN_AGENT",
        {
            "persona": persona,
            "objective": objective,
            "field_spec": _field_spec(fields),
            "time_notice": time_notice or _NO_TIME_NOTICE,
            "closing_line": closing_line,
            "conversation_history": json.dumps(history),
            "callee_reply": callee_speech,
        },
    )


async def generate_summary(*, persona: str, objective: str, history: list[dict], extracted_fields: dict) -> dict:
    """Returns {"summary_text": str, "extracted_fields": {...}}."""
    return await _invoke(
        "SUMMARY_AGENT",
        {
            "persona": persona,
            "objective": objective,
            "conversation_history": json.dumps(history),
            "extracted_fields": json.dumps(extracted_fields),
        },
    )
