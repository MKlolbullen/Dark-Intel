"""Lazy factory for LLM adapters. Import-time errors if the chosen
provider's SDK isn't installed are deferred to first use, not startup."""

from __future__ import annotations

from ..config import Config
from .base import LLMClient

_default: LLMClient | None = None
_relation: LLMClient | None = None


def _build(provider: str, model: str) -> LLMClient:
    provider = (provider or "").lower()
    if provider == "anthropic":
        from .anthropic_client import AnthropicAdapter

        if not Config.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY is required for LLM_PROVIDER=anthropic")
        return AnthropicAdapter(model=model, api_key=Config.ANTHROPIC_API_KEY)

    if provider == "gemini":
        from .gemini_client import GeminiAdapter

        if not Config.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is required for LLM_PROVIDER=gemini")
        return GeminiAdapter(model=model, api_key=Config.GEMINI_API_KEY)

    if provider == "grok":
        from .grok_client import GrokAdapter

        if not Config.GROK_API_KEY:
            raise RuntimeError("GROK_API_KEY is required for LLM_PROVIDER=grok")
        return GrokAdapter(model=model, api_key=Config.GROK_API_KEY)

    raise RuntimeError(
        f"Unknown LLM_PROVIDER={provider!r}. Expected one of: anthropic, gemini, grok."
    )


def get_default_client() -> LLMClient:
    """Client for long-form tasks (RAG answer, comparison, follow-up Q&A, discovery)."""

    global _default
    if _default is None:
        _default = _build(Config.LLM_PROVIDER, Config.default_model())
    return _default


def get_relation_client() -> LLMClient:
    """Client for high-volume cheap classification (edge inference, sentiment)."""

    global _relation
    if _relation is None:
        _relation = _build(Config.LLM_PROVIDER, Config.relation_model())
    return _relation


def reset() -> None:
    """Drop the cached singletons — mostly useful for tests."""

    global _default, _relation
    _default = None
    _relation = None
