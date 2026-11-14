from abc import ABC, abstractmethod
from typing import Any


class BaseAIProvider(ABC):
    """
    Abstract interface for all BridgeMate AI providers.
    Supports English and Amharic with grounded context.
    """

    @abstractmethod
    async def generate(
        self,
        question: str,
        context: list[dict[str, Any]],
        language: str = "en",
        system_instruction: str | None = None,
    ) -> str:
        """
        Generate grounded assistant response.
        :param question: Learner's query
        :param context: List of validated context items / document chunks
        :param language: 'en' for English or 'am' for Amharic
        :param system_instruction: Custom system prompt instructions
        :return: Generated response string
        """
        raise NotImplementedError
