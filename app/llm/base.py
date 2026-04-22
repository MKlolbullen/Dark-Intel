from __future__ import annotations

from abc import ABC, abstractmethod


class LLMClient(ABC):
    """Minimal adapter every provider implements.

    `thinking=True` asks for adaptive-style reasoning where the provider
    supports it; adapters silently ignore when they don't.

    `schema` is a JSON Schema dict. Anthropic enforces it strictly;
    Gemini and Grok convey it in the system prompt under JSON mode.

    Both `complete_json` variants return `None` if the provider errored
    or if the output wasn't parseable JSON. Callers handle that case.
    """

    def __init__(self, model: str):
        self.model = model

    @abstractmethod
    def complete(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 4096,
        thinking: bool = False,
    ) -> str:
        ...

    @abstractmethod
    async def acomplete(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 4096,
        thinking: bool = False,
    ) -> str:
        ...

    @abstractmethod
    def complete_json(
        self,
        system: str,
        user: str,
        *,
        schema: dict | None = None,
        max_tokens: int = 4096,
        thinking: bool = False,
    ) -> dict | None:
        ...

    @abstractmethod
    async def acomplete_json(
        self,
        system: str,
        user: str,
        *,
        schema: dict | None = None,
        max_tokens: int = 4096,
        thinking: bool = False,
    ) -> dict | None:
        ...
