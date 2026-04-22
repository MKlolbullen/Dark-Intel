"""Provider-agnostic LLM adapter layer.

Call sites go through `get_default_client()` (long-form tasks: RAG,
competitor discovery, comparison, follow-up Q&A) or
`get_relation_client()` (high-volume, cheap classification: edge
inference, sentiment scoring). The concrete provider is picked once
per process from `Config.LLM_PROVIDER` — "anthropic" | "gemini" | "grok".

Anthropic keeps full fidelity (strict JSON schemas, adaptive thinking).
Gemini and Grok are best-effort equivalents: JSON mime / json_object
mode with the schema conveyed in the system prompt, and
provider-native reasoning toggles where available.
"""

from __future__ import annotations

from .base import LLMClient
from .factory import get_default_client, get_relation_client, reset

__all__ = ["LLMClient", "get_default_client", "get_relation_client", "reset"]
