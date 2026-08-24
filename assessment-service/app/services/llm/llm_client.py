import asyncio
import json
import logging
import re
from functools import lru_cache
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.config import Settings, get_settings
from app.core.exceptions import LLMProviderError
from app.services.llm.azure_openai_provider import AzureOpenAIProvider
from app.services.llm.base import LLMProvider
from app.services.llm.claude_provider import ClaudeProvider

logger = logging.getLogger("app.llm")

T = TypeVar("T", bound=BaseModel)

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _extract_json_text(raw: str) -> str:
    match = _JSON_FENCE_RE.search(raw)
    if match:
        return match.group(1)
    return raw.strip()


class LLMClient:
    """Tries the primary provider first, falls back to the secondary on any failure.

    Each provider gets one retry if the response comes back but fails JSON/schema
    validation (models occasionally wrap JSON in prose despite instructions).
    """

    def __init__(self, providers: list[LLMProvider], timeout_seconds: int):
        if not providers:
            raise ValueError("LLMClient requires at least one provider")
        self._providers = providers
        self._timeout_seconds = timeout_seconds

    async def get_json(self, system_prompt: str, user_prompt: str, schema_model: type[T]) -> T:
        errors: list[str] = []
        for provider in self._providers:
            for attempt in (1, 2):
                try:
                    raw = await asyncio.wait_for(
                        provider.complete_json(system_prompt, user_prompt),
                        timeout=self._timeout_seconds,
                    )
                    data = json.loads(_extract_json_text(raw))
                    return schema_model.model_validate(data)
                except (asyncio.TimeoutError, json.JSONDecodeError, ValidationError) as exc:
                    msg = f"{provider.name} attempt {attempt} failed: {exc}"
                    logger.warning(msg)
                    errors.append(msg)
                    continue
                except Exception as exc:  # provider/network/auth errors - don't retry same provider
                    msg = f"{provider.name} raised {exc.__class__.__name__}: {exc}"
                    logger.warning(msg)
                    errors.append(msg)
                    break

        logger.error("All LLM providers failed: %s", errors)
        raise LLMProviderError("All configured LLM providers failed to produce a valid response")


def _build_provider(name: str, settings: Settings) -> LLMProvider:
    if name == "claude":
        return ClaudeProvider(
            api_key=settings.ANTHROPIC_API_KEY,
            model=settings.ANTHROPIC_MODEL,
            max_output_tokens=settings.LLM_MAX_OUTPUT_TOKENS,
        )
    if name == "azure_openai":
        return AzureOpenAIProvider(
            api_key=settings.AZURE_OPENAI_API_KEY,
            endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_version=settings.AZURE_OPENAI_API_VERSION,
            deployment=settings.AZURE_OPENAI_DEPLOYMENT,
            max_output_tokens=settings.LLM_MAX_OUTPUT_TOKENS,
        )
    raise ValueError(f"Unknown LLM provider: {name}")


@lru_cache
def get_llm_client() -> LLMClient:
    settings = get_settings()
    providers = [
        _build_provider(settings.LLM_PRIMARY_PROVIDER, settings),
        _build_provider(settings.LLM_FALLBACK_PROVIDER, settings),
    ]
    return LLMClient(providers=providers, timeout_seconds=settings.LLM_TIMEOUT_SECONDS)
