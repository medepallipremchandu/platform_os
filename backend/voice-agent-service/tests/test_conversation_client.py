"""Verifies app/services/conversation_client.py's variable-building and error handling without
ever calling a real agent-builder-service - httpx is monkeypatched at the AsyncClient.post level.
"""
import pytest

from app.core.exceptions import ConversationAgentError
from app.services import conversation_client


class _FakeResponse:
    def __init__(self, status_code: int, json_body: dict):
        self.status_code = status_code
        self._json_body = json_body
        self.text = str(json_body)

    def json(self):
        return self._json_body


class _FakeAsyncClient:
    def __init__(self, response: _FakeResponse, captured: dict):
        self._response = response
        self._captured = captured

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json=None, headers=None):
        self._captured["url"] = url
        self._captured["json"] = json
        self._captured["headers"] = headers
        return self._response


def _patch_agent(monkeypatch, agent_prefix: str):
    monkeypatch.setattr(
        "app.services.conversation_client.get_settings",
        lambda: type(
            "S",
            (),
            {
                f"{agent_prefix}_CLIENT_ID": "cid",
                f"{agent_prefix}_CLIENT_SECRET": "csecret",
                "AGENT_BUILDER_SERVICE_URL": "https://agent-builder.invalid/api/v1",
                "AGENT_INVOKE_TIMEOUT_SECONDS": 5.0,
            },
        )(),
    )

    async def fake_get_token(client_id, client_secret):
        assert client_id == "cid"
        assert client_secret == "csecret"
        return "fake-access-token"

    monkeypatch.setattr("app.services.conversation_client.token_cache.get_token", fake_get_token)


async def test_consent_turn_sends_expected_variables(monkeypatch):
    _patch_agent(monkeypatch, "CONSENT_TURN_AGENT")
    captured: dict = {}
    response = _FakeResponse(200, {"output": {"consent": "yes", "ai_response": ""}})
    monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeAsyncClient(response, captured))

    result = await conversation_client.consent_turn(persona="You are Ava.", consent_line="Do you consent?", callee_speech="yes")

    assert result == {"consent": "yes", "ai_response": ""}
    assert captured["json"]["variables"] == {
        "persona": "You are Ava.",
        "consent_line": "Do you consent?",
        "callee_reply": "yes",
    }
    assert captured["headers"]["Authorization"] == "Bearer fake-access-token"


async def test_main_turn_json_stringifies_history_and_field_spec(monkeypatch):
    _patch_agent(monkeypatch, "MAIN_TURN_AGENT")
    captured: dict = {}
    response = _FakeResponse(200, {"output": {"ai_response": "ok", "fields": {}, "done": False}})
    monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeAsyncClient(response, captured))

    await conversation_client.main_turn(
        persona="You are Ava.",
        objective="Confirm the time.",
        fields=[{"name": "preferred_time", "type": "string", "description": "when"}],
        closing_line="Bye!",
        history=[{"speaker": "ai", "text": "hi"}],
        callee_speech="tomorrow at 3",
    )

    variables = captured["json"]["variables"]
    assert isinstance(variables["conversation_history"], str)
    assert "hi" in variables["conversation_history"]
    assert isinstance(variables["field_spec"], str)
    assert "preferred_time" in variables["field_spec"]
    assert variables["time_notice"] == "No time notice needed for this turn."


async def test_non_json_output_raises_conversation_agent_error(monkeypatch):
    _patch_agent(monkeypatch, "SUMMARY_AGENT")
    captured: dict = {}
    response = _FakeResponse(200, {"output": "not json at all"})
    monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeAsyncClient(response, captured))

    with pytest.raises(ConversationAgentError):
        await conversation_client.generate_summary(persona="p", objective="o", history=[], extracted_fields={})


async def test_missing_credentials_raises_conversation_agent_error(monkeypatch):
    monkeypatch.setattr(
        "app.services.conversation_client.get_settings",
        lambda: type("S", (), {"CONSENT_TURN_AGENT_CLIENT_ID": "", "CONSENT_TURN_AGENT_CLIENT_SECRET": ""})(),
    )
    with pytest.raises(ConversationAgentError):
        await conversation_client.consent_turn(persona="p", consent_line="c", callee_speech="hi")
