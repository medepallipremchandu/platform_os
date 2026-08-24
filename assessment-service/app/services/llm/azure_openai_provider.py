import logging

from openai import AsyncAzureOpenAI

from app.services.llm.base import LLMProvider

logger = logging.getLogger("app.llm.azure_openai")


class AzureOpenAIProvider(LLMProvider):
    name = "azure_openai"

    def __init__(self, api_key: str, endpoint: str, api_version: str, deployment: str, max_output_tokens: int):
        self._client = AsyncAzureOpenAI(api_key=api_key, azure_endpoint=endpoint, api_version=api_version)
        self._deployment = deployment
        self._max_output_tokens = max_output_tokens

    async def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        response = await self._client.chat.completions.create(
            model=self._deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_completion_tokens=self._max_output_tokens,
            response_format={"type": "json_object"},
        )
        if response.choices[0].finish_reason == "length":
            logger.warning(
                "Azure OpenAI response was truncated at max_completion_tokens=%d - JSON will likely fail "
                "to parse. Increase LLM_MAX_OUTPUT_TOKENS if this recurs.",
                self._max_output_tokens,
            )
        return response.choices[0].message.content or ""
