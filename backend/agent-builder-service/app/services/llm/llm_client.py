import asyncio
import json
import logging
import re

from app.services.llm.azure_openai_provider import AzureOpenAIProvider
from app.services.llm.base import LLMProvider
from app.services.llm.claude_provider import ClaudeProvider

logger = logging.getLogger("app.llm")

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _extract_json_text(raw: str) -> str:
    match = _JSON_FENCE_RE.search(raw)
    return match.group(1) if match else raw.strip()


def try_parse_json(raw: str):
    """Best-effort JSON parse for agent output. Returns the parsed object if the text is
    JSON (optionally fenced), otherwise returns the raw string unchanged - agent-builder-service
    is generic and doesn't know whether a given agent is supposed to produce JSON or prose."""
    try:
        return json.loads(_extract_json_text(raw))
    except (json.JSONDecodeError, ValueError):
        return raw


class InvokeResult:
    def __init__(self, output, provider_used: str, raw_text: str):
        self.output = output
        self.provider_used = provider_used
        self.raw_text = raw_text


class LLMClient:
    """Tries the primary provider, falling back to the secondary on any failure (timeout,
    auth error, network error, rate limit). One retry per provider on a transient failure."""

    def __init__(self, providers: list[LLMProvider], timeout_seconds: float):
        if not providers:
            raise ValueError("LLMClient requires at least one provider")
        self._providers = providers
        self._timeout_seconds = timeout_seconds

    async def invoke(self, system_prompt: str, user_prompt: str) -> InvokeResult:
        errors: list[str] = []
        for provider in self._providers:
            for attempt in (1, 2):
                try:
                    raw = await asyncio.wait_for(
                        provider.complete_json(system_prompt, user_prompt),
                        timeout=self._timeout_seconds,
                    )
                    return InvokeResult(output=try_parse_json(raw), provider_used=provider.name, raw_text=raw)
                except asyncio.TimeoutError as exc:
                    msg = f"{provider.name} attempt {attempt} timed out: {exc}"
                    logger.warning(msg)
                    errors.append(msg)
                    continue
                except Exception as exc:  # provider/network/auth errors - don't retry same provider
                    msg = f"{provider.name} raised {exc.__class__.__name__}: {exc}"
                    logger.warning(msg)
                    errors.append(msg)
                    break

        raise RuntimeError(f"All configured models failed: {errors}")


def build_provider(provider: str, api_key: str, model_id: str, max_output_tokens: int, **kwargs) -> LLMProvider:
    if provider == "claude":
        return ClaudeProvider(api_key=api_key, model=model_id, max_output_tokens=max_output_tokens)
    if provider == "azure_openai":
        return AzureOpenAIProvider(
            api_key=api_key,
            endpoint=kwargs["endpoint"],
            api_version=kwargs["api_version"],
            deployment=model_id,
            max_output_tokens=max_output_tokens,
        )
    raise ValueError(f"Unknown provider: {provider}")
