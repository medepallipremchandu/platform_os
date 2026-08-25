"""One-time setup: registers the 3 conversation agents this service depends on in
agent-builder-service (Consent Turn, Main Conversation Turn, Summary), publishes each to mint
its IAM invoke credential, and prints the client_id/client_secret pairs to copy into this
service's own .env as CONSENT_TURN_AGENT_CLIENT_ID/_SECRET etc.

Unlike agent-builder-service's own scripts/seed_models_and_agents.py (which runs in-process and
calls app.services.agent_service directly, since it lives in that same codebase),
voice-agent-service is a separate service - this script talks to agent-builder-service entirely
over its HTTP API, the same way any other consumer would.

Prerequisites:
  - agent-builder-service running and reachable at AGENT_BUILDER_SERVICE_URL.
  - agent-builder-service already has at least one active Model registered (run its own
    scripts/seed_models_and_agents.py first if not - this script does not register models
    itself, it only reads the existing catalog via GET /models).
  - iam-service running and reachable, with IAM_BOOTSTRAP_ADMIN_EMAIL/PASSWORD and
    BOOTSTRAP_ORGANIZATION_ID set in .env (same admin used by scripts/bootstrap_iam_identity.py),
    and that admin's role must carry talentos.agentbuilder.{models,agents}.read/write/publish
    (the built-in "Organization Admin" role does).

The prompts below port the reference implementation's app/services/conversation.py
(_consent_system_prompt / _main_system_prompt / _summary_system_prompt) into agent-builder-
service's {{variable}} template syntax - plain substitution, no logic - with the callee/candidate
speech always carried in a JSON *variable*, never interpolated into the instruction text
(mitigates prompt injection, same rule the reference repo followed).

Usage (from voice-agent-service/):
    .venv/Scripts/python.exe scripts/seed_call_agents.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from app.config import get_settings  # noqa: E402

_JSON_KEYS_NOTE = "Always respond with ONLY a single valid JSON object, no prose, no markdown fences"

CONSENT_TURN_AGENT = {
    "name": "Voice Agent - Consent Turn",
    "description": "Determines whether a call recipient consents to continuing an AI-driven call.",
    "system_prompt": """You are an AI voice agent. {{persona}}

You have just said to the callee: "{{consent_line}}"

Your ONLY job right now is to determine whether the callee consents to continue (recording + being spoken with by an AI). Do NOT pursue the call objective yet.

The callee may not answer directly - they may ask a question or say something unrelated. If so, give a brief, polite reply, then clearly re-ask for a yes or no.

{_JSON_KEYS_NOTE}, with these exact keys:
{{
    "consent": "<yes, no, or unclear>",
    "ai_response": "<what to say next; used only when consent is 'unclear', otherwise empty string>"
}}

Do NOT infer or report the callee's emotional state, mood, affect, or sentiment.""".format(_JSON_KEYS_NOTE=_JSON_KEYS_NOTE),
    "user_prompt_template": "The callee just said: {{callee_reply}}",
}

MAIN_TURN_AGENT = {
    "name": "Voice Agent - Main Conversation Turn",
    "description": "Generates the next spoken turn of an in-progress AI voice call and extracts structured fields.",
    "system_prompt": """You are an AI voice agent. {{persona}}

Objective: {{objective}}

You need to collect the following structured fields over the course of the conversation (a JSON schema, not something to read aloud to the callee):
{{field_spec}}

{{time_notice}}

When the objective is complete or the callee wants to end the call, set "done": true and use "{{closing_line}}" (or a natural variation of it) as part of your closing ai_response.

{_JSON_KEYS_NOTE}, with these exact keys:
{{
    "ai_response": "<your conversational reply to speak to the callee>",
    "fields": {{<one key per field above, current best-known value or empty string if not yet known>}},
    "done": <true or false>
}}

Do NOT infer or report the callee's emotional state, mood, affect, or sentiment.""".format(_JSON_KEYS_NOTE=_JSON_KEYS_NOTE),
    "user_prompt_template": """Conversation history so far (JSON array of {{"speaker", "text"}} objects):
{{conversation_history}}

The callee just said: {{callee_reply}}""",
}

SUMMARY_AGENT = {
    "name": "Voice Agent - Summary",
    "description": "Summarizes a completed AI voice call and finalizes its extracted fields.",
    "system_prompt": """You are summarizing a completed AI voice call. {{persona}}
Objective was: {{objective}}

Given the full conversation transcript and the fields extracted, write a concise, factual summary (3-5 sentences) for the business that requested this call.

{_JSON_KEYS_NOTE}, with these exact keys:
{{
    "summary_text": "<concise natural-language summary>",
    "extracted_fields": {{<final best-known value for each requested field>}}
}}""".format(_JSON_KEYS_NOTE=_JSON_KEYS_NOTE),
    "user_prompt_template": """Conversation transcript (JSON array of {{"speaker", "text"}} objects):
{{conversation_history}}

Fields extracted so far (JSON object):
{{extracted_fields}}""",
}

AGENTS = [
    ("CONSENT_TURN_AGENT", CONSENT_TURN_AGENT),
    ("MAIN_TURN_AGENT", MAIN_TURN_AGENT),
    ("SUMMARY_AGENT", SUMMARY_AGENT),
]


def _get_admin_token(iam_url: str, email: str, password: str, organization_id: str) -> str:
    with httpx.Client(base_url=iam_url, timeout=15.0) as client:
        resp = client.post(
            "/auth/login", json={"email": email, "password": password, "organization_id": organization_id}
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


def _pick_models(client: httpx.Client, headers: dict) -> tuple[str, str | None]:
    resp = client.get("/models", headers=headers)
    resp.raise_for_status()
    models = resp.json()
    if not models:
        raise SystemExit(
            "agent-builder-service has no active Model registered yet - run its own "
            "scripts/seed_models_and_agents.py first (from agent-builder-service/)."
        )
    primary = next((m for m in models if m["provider"] == "claude"), models[0])
    fallback = next((m for m in models if m["id"] != primary["id"]), None)
    return primary["id"], (fallback["id"] if fallback else None)


def main() -> None:
    settings = get_settings()
    if not settings.IAM_BOOTSTRAP_ADMIN_EMAIL or not settings.IAM_BOOTSTRAP_ADMIN_PASSWORD:
        raise SystemExit("IAM_BOOTSTRAP_ADMIN_EMAIL / IAM_BOOTSTRAP_ADMIN_PASSWORD must be set in .env")
    if not settings.BOOTSTRAP_ORGANIZATION_ID:
        raise SystemExit("BOOTSTRAP_ORGANIZATION_ID must be set in .env")

    admin_token = _get_admin_token(
        settings.IAM_SERVICE_URL,
        settings.IAM_BOOTSTRAP_ADMIN_EMAIL,
        settings.IAM_BOOTSTRAP_ADMIN_PASSWORD,
        settings.BOOTSTRAP_ORGANIZATION_ID,
    )
    headers = {"Authorization": f"Bearer {admin_token}"}

    with httpx.Client(base_url=settings.AGENT_BUILDER_SERVICE_URL, timeout=30.0) as client:
        primary_model_id, fallback_model_id = _pick_models(client, headers)

        print(f"{'Agent':<40} {'Code':<8} client_id / client_secret (copy now - shown once)")
        print("-" * 110)
        for env_prefix, spec in AGENTS:
            create_resp = client.post(
                "/agents",
                json={
                    "name": spec["name"],
                    "description": spec["description"],
                    "system_prompt": spec["system_prompt"],
                    "user_prompt_template": spec["user_prompt_template"],
                    "primary_model_id": primary_model_id,
                    "fallback_model_id": fallback_model_id,
                },
                headers=headers,
            )
            create_resp.raise_for_status()
            agent = create_resp.json()

            publish_resp = client.post(f"/agents/{agent['id']}/publish", headers=headers)
            publish_resp.raise_for_status()
            published = publish_resp.json()
            client_secret = published["client_secret"]

            keys_resp = client.get(f"/agents/{agent['id']}/keys", headers=headers)
            keys_resp.raise_for_status()
            keys = keys_resp.json()
            client_id = next((k["client_id"] for k in keys if k["revoked_at"] is None), None)

            print(f"{agent['name']:<40} {agent['agent_code']:<8} {client_id} / {client_secret}")
            print(f"  -> {env_prefix}_CLIENT_ID={client_id}")
            print(f"  -> {env_prefix}_CLIENT_SECRET={client_secret}")

    print()
    print("Copy the CLIENT_ID/CLIENT_SECRET lines above into voice-agent-service/.env.")


if __name__ == "__main__":
    main()
