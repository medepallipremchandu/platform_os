from abc import ABC, abstractmethod


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        """Send the prompt to the model and return the raw text response.

        The caller is responsible for parsing/validating the JSON contained in it.
        """
        raise NotImplementedError
