import logging

from anthropic import AsyncAnthropic

from app.services.llm.base import LLMProvider

logger = logging.getLogger("app.llm.claude")


class ClaudeProvider(LLMProvider):
    name = "claude"

    def __init__(self, api_key: str, model: str, max_output_tokens: int):
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model
        self._max_output_tokens = max_output_tokens

    async def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=self._max_output_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        if response.stop_reason == "max_tokens":
            logger.warning(
                "Claude response was truncated at max_tokens=%d - JSON will likely fail to parse. "
                "Increase LLM_MAX_OUTPUT_TOKENS if this recurs.",
                self._max_output_tokens,
            )
        return "".join(block.text for block in response.content if block.type == "text")
