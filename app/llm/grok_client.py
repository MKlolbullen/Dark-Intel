from __future__ import annotations

import json

from openai import AsyncOpenAI, OpenAI

from .base import LLMClient

GROK_BASE_URL = "https://api.x.ai/v1"
_SCHEMA_HINT = (
    "\n\nReturn a single valid JSON object. No prose, no markdown fences. "
    "Conform to this JSON schema:\n"
)


class GrokAdapter(LLMClient):
    """xAI Grok via the openai SDK pointed at api.x.ai.

    Reasoning models (e.g. grok-3-mini, grok-4) accept `reasoning_effort`.
    When the server rejects it (older model), the adapter retries
    without. JSON mode uses response_format={"type": "json_object"};
    schema is included in the system prompt as a hint.
    """

    def __init__(self, model: str, api_key: str):
        super().__init__(model)
        self._client = OpenAI(api_key=api_key, base_url=GROK_BASE_URL)
        self._aclient = AsyncOpenAI(api_key=api_key, base_url=GROK_BASE_URL)

    def _messages(self, system: str, user: str) -> list[dict]:
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    def _augment_system(self, system: str, schema: dict | None) -> str:
        if schema is None:
            return system
        return f"{system}{_SCHEMA_HINT}{json.dumps(schema)}"

    def _call_sync(self, messages, max_tokens, thinking, response_format):
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if response_format is not None:
            kwargs["response_format"] = response_format
        if thinking:
            kwargs["reasoning_effort"] = "high"
        try:
            return self._client.chat.completions.create(**kwargs)
        except Exception:
            if thinking:
                kwargs.pop("reasoning_effort", None)
                return self._client.chat.completions.create(**kwargs)
            raise

    async def _call_async(self, messages, max_tokens, thinking, response_format):
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if response_format is not None:
            kwargs["response_format"] = response_format
        if thinking:
            kwargs["reasoning_effort"] = "high"
        try:
            return await self._aclient.chat.completions.create(**kwargs)
        except Exception:
            if thinking:
                kwargs.pop("reasoning_effort", None)
                return await self._aclient.chat.completions.create(**kwargs)
            raise

    def complete(self, system, user, *, max_tokens=4096, thinking=False) -> str:
        response = self._call_sync(
            self._messages(system, user), max_tokens, thinking, None
        )
        return response.choices[0].message.content or ""

    async def acomplete(self, system, user, *, max_tokens=4096, thinking=False) -> str:
        response = await self._call_async(
            self._messages(system, user), max_tokens, thinking, None
        )
        return response.choices[0].message.content or ""

    def complete_json(
        self, system, user, *, schema=None, max_tokens=4096, thinking=False
    ) -> dict | None:
        sys = self._augment_system(system, schema)
        try:
            response = self._call_sync(
                self._messages(sys, user),
                max_tokens,
                thinking,
                {"type": "json_object"},
            )
            text = (response.choices[0].message.content or "").strip()
            return json.loads(text) if text else None
        except Exception:
            return None

    async def acomplete_json(
        self, system, user, *, schema=None, max_tokens=4096, thinking=False
    ) -> dict | None:
        sys = self._augment_system(system, schema)
        try:
            response = await self._call_async(
                self._messages(sys, user),
                max_tokens,
                thinking,
                {"type": "json_object"},
            )
            text = (response.choices[0].message.content or "").strip()
            return json.loads(text) if text else None
        except Exception:
            return None
