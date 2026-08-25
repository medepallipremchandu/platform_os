"""Proves the exchange-then-invoke mechanics work: client_id/client_secret -> iam-service
POST /auth/token -> cached access token -> agent-builder-service POST /invoke with
Authorization: Bearer <token>. Both iam-service and agent-builder-service are mocked here -
this does NOT make a real call to either service (see final report: that requires the real
per-agent credentials from agent-builder-service's own IAM migration).
"""
import asyncio
from unittest.mock import patch

import httpx
import pytest

from app.core.iam_client import AgentCredentialTokenCache
from app.core.exceptions import LLMProviderError
from app.services import agent_client


def run(coro):
    return asyncio.run(coro)


class _FakeResponse:
    def __init__(self, status_code: int, json_body: dict):
        self.status_code = status_code
        self._json_body = json_body
        self.text = str(json_body)

    def json(self):
        return self._json_body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)


@pytest.fixture(autouse=True)
def _isolated_token_cache(monkeypatch):
    """Each test gets its own cache instance so cached tokens never leak between tests."""
    cache = AgentCredentialTokenCache()
    monkeypatch.setattr("app.services.agent_client.agent_token_cache", cache)
    return cache


def test_invoke_exchanges_credentials_then_calls_agent_builder(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("JD_ANALYSIS_AGENT_CLIENT_ID", "sp_test_client_id")
    monkeypatch.setenv("JD_ANALYSIS_AGENT_CLIENT_SECRET", "sp_test_client_secret")
    get_settings.cache_clear()

    token_response = _FakeResponse(200, {"access_token": "fake.jwt.token", "token_type": "bearer", "expires_in": 900})
    invoke_response = _FakeResponse(200, {"output": {"job_title": "Engineer"}})

    async def fake_post(self, url, json=None, headers=None, **kwargs):
        if url.endswith("/auth/token"):
            assert json == {"client_id": "sp_test_client_id", "client_secret": "sp_test_client_secret"}
            return token_response
        if url.endswith("/invoke"):
            assert headers["Authorization"] == "Bearer fake.jwt.token"
            return invoke_response
        raise AssertionError(f"Unexpected URL {url}")

    try:
        with patch("httpx.AsyncClient.post", new=fake_post):
            result = run(agent_client.invoke("JD_ANALYSIS_AGENT", {"jd_text": "some jd"}))
        assert result == {"job_title": "Engineer"}
    finally:
        get_settings.cache_clear()


def test_token_cache_reuses_token_until_near_expiry():
    cache = AgentCredentialTokenCache()
    calls = {"count": 0}

    async def fake_exchange(self, client_id, client_secret):
        calls["count"] += 1
        return "token-a", 900

    with patch.object(AgentCredentialTokenCache, "_exchange", new=fake_exchange):
        token1 = run(cache.get_token("cid", "secret"))
        token2 = run(cache.get_token("cid", "secret"))

    assert token1 == token2 == "token-a"
    assert calls["count"] == 1  # second call served from cache, no re-exchange


def test_token_cache_refreshes_near_expiry():
    cache = AgentCredentialTokenCache()
    calls = {"count": 0}

    async def fake_exchange(self, client_id, client_secret):
        calls["count"] += 1
        return f"token-{calls['count']}", 30  # below the 60s refresh margin - always "near expiry"

    with patch.object(AgentCredentialTokenCache, "_exchange", new=fake_exchange):
        token1 = run(cache.get_token("cid", "secret"))
        token2 = run(cache.get_token("cid", "secret"))

    assert token1 == "token-1"
    assert token2 == "token-2"
    assert calls["count"] == 2


def test_invoke_raises_without_configured_credentials(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("MATCHING_AGENT_CLIENT_ID", "")
    monkeypatch.setenv("MATCHING_AGENT_CLIENT_SECRET", "")
    get_settings.cache_clear()

    try:
        with pytest.raises(LLMProviderError):
            run(agent_client.invoke("MATCHING_AGENT", {}))
    finally:
        get_settings.cache_clear()
