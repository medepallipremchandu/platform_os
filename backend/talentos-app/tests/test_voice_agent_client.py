"""Proves the exchange-then-call mechanics work: client_id/client_secret -> iam-service
POST /auth/token -> cached access token -> voice-agent-service with Authorization: Bearer <token>.
Both iam-service and voice-agent-service are mocked here - voice-agent-service was not reachable
while this was written (see final report: a live pass against the real service is still needed).
"""
import asyncio
from unittest.mock import patch

import httpx
import pytest

from app.core.exceptions import AppException
from app.core.iam_client import AgentCredentialTokenCache
from app.services import voice_agent_client


def run(coro):
    return asyncio.run(coro)


class _FakeResponse:
    def __init__(self, status_code: int, json_body):
        self.status_code = status_code
        self._json_body = json_body
        self.text = str(json_body)

    def json(self):
        return self._json_body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)


_TOKEN_RESPONSE = _FakeResponse(200, {"access_token": "tok", "token_type": "bearer", "expires_in": 900})


async def _fake_token_post(self, url, json=None, headers=None, **kwargs):
    # Matches httpx.AsyncClient.post's real signature - used by iam_client._exchange.
    assert url.endswith("/auth/token")
    assert json == {"client_id": "sp_test_client_id", "client_secret": "sp_test_client_secret"}
    return _TOKEN_RESPONSE


@pytest.fixture(autouse=True)
def _isolated_token_cache(monkeypatch):
    """Each test gets its own cache instance so cached tokens never leak between tests."""
    cache = AgentCredentialTokenCache()
    monkeypatch.setattr("app.services.voice_agent_client.agent_token_cache", cache)
    return cache


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    from app.config import get_settings

    yield
    get_settings.cache_clear()


def _configure_credentials(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("VOICE_AGENT_CLIENT_ID", "sp_test_client_id")
    monkeypatch.setenv("VOICE_AGENT_CLIENT_SECRET", "sp_test_client_secret")
    get_settings.cache_clear()


def test_list_call_agents_exchanges_credentials_then_calls_voice_agent_service(monkeypatch):
    _configure_credentials(monkeypatch)
    list_response = _FakeResponse(200, [{"id": "cac-1", "name": "Screening v1", "description": "x"}])

    async def fake_request(self, method, url, json=None, params=None, headers=None, **kwargs):
        assert method == "GET"
        assert url.endswith("/call-agents")
        assert headers["Authorization"] == "Bearer tok"
        return list_response

    with patch("httpx.AsyncClient.post", new=_fake_token_post), patch("httpx.AsyncClient.request", new=fake_request):
        result = run(voice_agent_client.list_call_agents())
    assert result == [{"id": "cac-1", "name": "Screening v1", "description": "x"}]


def test_create_call_posts_expected_payload(monkeypatch):
    _configure_credentials(monkeypatch)
    create_response = _FakeResponse(202, {"id": "call-1", "status": "queued", "to_number": "+15550001111"})
    seen = {}

    async def fake_request(self, method, url, json=None, params=None, headers=None, **kwargs):
        assert url.endswith("/calls")
        seen["method"] = method
        seen["json"] = json
        seen["headers"] = headers
        return create_response

    with patch("httpx.AsyncClient.post", new=_fake_token_post), patch("httpx.AsyncClient.request", new=fake_request):
        result = run(
            voice_agent_client.create_call("cac-1", "+15550001111", webhook_url="https://example.com/webhook?secret=s")
        )
    assert result["id"] == "call-1"
    assert seen["method"] == "POST"
    assert seen["json"] == {
        "call_agent_config_id": "cac-1",
        "to_number": "+15550001111",
        "webhook_url": "https://example.com/webhook?secret=s",
    }
    assert seen["headers"]["Authorization"] == "Bearer tok"


def test_get_call_and_conversation_and_summary_and_cancel(monkeypatch):
    _configure_credentials(monkeypatch)
    responses = {
        "/calls/call-1": _FakeResponse(200, {"id": "call-1", "status": "dialing"}),
        "/calls/call-1/conversation": _FakeResponse(200, [{"turn_index": 0, "speaker": "ai", "text": "Hello"}]),
        "/calls/call-1/summary": _FakeResponse(200, {"summary_text": "Good fit", "extracted_fields": {"years": 5}}),
        "/calls/call-1/cancel": _FakeResponse(200, {"id": "call-1", "status": "cancelled"}),
    }

    async def fake_request(self, method, url, json=None, params=None, headers=None, **kwargs):
        for suffix, response in responses.items():
            if url.endswith(suffix):
                return response
        raise AssertionError(f"Unexpected URL {url}")

    with patch("httpx.AsyncClient.post", new=_fake_token_post), patch("httpx.AsyncClient.request", new=fake_request):
        call = run(voice_agent_client.get_call("call-1"))
        conversation = run(voice_agent_client.get_conversation("call-1"))
        summary = run(voice_agent_client.get_summary("call-1"))
        cancelled = run(voice_agent_client.cancel_call("call-1"))

    assert call["status"] == "dialing"
    assert conversation[0]["text"] == "Hello"
    assert summary["extracted_fields"] == {"years": 5}
    assert cancelled["status"] == "cancelled"


def test_get_summary_returns_none_when_service_returns_null(monkeypatch):
    _configure_credentials(monkeypatch)

    async def fake_request(self, method, url, json=None, params=None, headers=None, **kwargs):
        return _FakeResponse(200, None)

    with patch("httpx.AsyncClient.post", new=_fake_token_post), patch("httpx.AsyncClient.request", new=fake_request):
        summary = run(voice_agent_client.get_summary("call-1"))
    assert summary is None


def test_request_raises_voice_agent_service_error_on_http_error(monkeypatch):
    _configure_credentials(monkeypatch)
    error_response = _FakeResponse(500, {"detail": "boom"})

    async def fake_request(self, method, url, json=None, params=None, headers=None, **kwargs):
        return error_response

    with patch("httpx.AsyncClient.post", new=_fake_token_post), patch("httpx.AsyncClient.request", new=fake_request):
        with pytest.raises(AppException):
            run(voice_agent_client.get_call("call-1"))


def test_request_raises_without_configured_credentials(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("VOICE_AGENT_CLIENT_ID", "")
    monkeypatch.setenv("VOICE_AGENT_CLIENT_SECRET", "")
    get_settings.cache_clear()

    with pytest.raises(AppException):
        run(voice_agent_client.list_call_agents())


def test_request_wraps_connection_error(monkeypatch):
    _configure_credentials(monkeypatch)

    async def fake_request(self, method, url, json=None, params=None, headers=None, **kwargs):
        raise httpx.ConnectError("connection refused", request=None)

    with patch("httpx.AsyncClient.post", new=_fake_token_post), patch("httpx.AsyncClient.request", new=fake_request):
        with pytest.raises(AppException):
            run(voice_agent_client.list_call_agents())
