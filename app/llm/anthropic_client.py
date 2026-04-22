from __future__ import annotations

import json

import anthropic

from .base import LLMClient


class AnthropicAdapter(LLMClient):
    """Full-fidelity Anthropic adapter: adaptive thinking + strict JSON schemas."""

    def __init__(self, model: str, api_key: str):
        super().__init__(model)
        self._client = anthropic.Anthropic(api_key=api_key)
        self._aclient = anthropic.AsyncAnthropic(api_key=api_key)

    def _kwargs(self, thinking: bool) -> dict:
        return {"thinking": {"type": "adaptive"}} if thinking else {}

    def _format_kwargs(self, schema: dict | None) -> dict:
        if not schema:
            return {}
        return {"output_config": {"format": {"type": "json_schema", "schema": schema}}}

    def _extract(self, response) -> str:
        return next((b.text for b in response.content if b.type == "text"), "")

    def complete(self, system, user, *, max_tokens=4096, thinking=False) -> str:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            **self._kwargs(thinking),
        )
        return self._extract(response)

    async def acomplete(self, system, user, *, max_tokens=4096, thinking=False) -> str:
        response = await self._aclient.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            **self._kwargs(thinking),
        )
        return self._extract(response)

    def complete_json(
        self, system, user, *, schema=None, max_tokens=4096, thinking=False
    ) -> dict | None:
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                **self._kwargs(thinking),
                **self._format_kwargs(schema),
            )
            text = self._extract(response).strip()
            return json.loads(text) if text else None
        except Exception:
            return None

    async def acomplete_json(
        self, system, user, *, schema=None, max_tokens=4096, thinking=False
    ) -> dict | None:
        try:
            response = await self._aclient.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                **self._kwargs(thinking),
                **self._format_kwargs(schema),
            )
            text = self._extract(response).strip()
            return json.loads(text) if text else None
        except Exception:
            return None
