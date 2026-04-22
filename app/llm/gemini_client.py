from __future__ import annotations

import asyncio
import json

from .base import LLMClient

_SCHEMA_HINT = (
    "\n\nReturn a single valid JSON object. No prose, no markdown fences. "
    "Conform to this JSON schema:\n"
)


class GeminiAdapter(LLMClient):
    """Google Gemini via the `google-genai` SDK.

    JSON mode uses `response_mime_type="application/json"`. Schema is
    passed through `response_schema` when the SDK accepts it and echoed
    in the system prompt as a hint regardless, so downstream parsing
    stays robust even if a particular schema trips the SDK up.
    """

    def __init__(self, model: str, api_key: str):
        super().__init__(model)
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self._genai = genai

    def _config(
        self,
        system: str,
        max_tokens: int,
        thinking: bool,
        schema: dict | None = None,
    ):
        types = self._genai.types
        kwargs = {
            "system_instruction": system,
            "max_output_tokens": max_tokens,
        }
        if schema is not None:
            kwargs["response_mime_type"] = "application/json"
            # Best effort: pass the schema, swallow if the SDK/model rejects it.
            try:
                kwargs["response_schema"] = schema
            except Exception:
                pass
        if thinking:
            try:
                kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=-1)
            except Exception:
                pass
        return types.GenerateContentConfig(**kwargs)

    def _augment_system(self, system: str, schema: dict | None) -> str:
        if schema is None:
            return system
        return f"{system}{_SCHEMA_HINT}{json.dumps(schema)}"

    def complete(self, system, user, *, max_tokens=4096, thinking=False) -> str:
        cfg = self._config(system, max_tokens, thinking)
        response = self._client.models.generate_content(
            model=self.model, contents=user, config=cfg
        )
        return getattr(response, "text", "") or ""

    async def acomplete(self, system, user, *, max_tokens=4096, thinking=False) -> str:
        cfg = self._config(system, max_tokens, thinking)
        response = await self._client.aio.models.generate_content(
            model=self.model, contents=user, config=cfg
        )
        return getattr(response, "text", "") or ""

    def complete_json(
        self, system, user, *, schema=None, max_tokens=4096, thinking=False
    ) -> dict | None:
        sys = self._augment_system(system, schema)
        cfg = self._config(sys, max_tokens, thinking, schema=schema)
        try:
            response = self._client.models.generate_content(
                model=self.model, contents=user, config=cfg
            )
            text = (getattr(response, "text", "") or "").strip()
            return json.loads(text) if text else None
        except Exception:
            return None

    async def acomplete_json(
        self, system, user, *, schema=None, max_tokens=4096, thinking=False
    ) -> dict | None:
        sys = self._augment_system(system, schema)
        cfg = self._config(sys, max_tokens, thinking, schema=schema)
        try:
            response = await self._client.aio.models.generate_content(
                model=self.model, contents=user, config=cfg
            )
            text = (getattr(response, "text", "") or "").strip()
            return json.loads(text) if text else None
        except Exception:
            return None
