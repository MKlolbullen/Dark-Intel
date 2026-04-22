"""Generate a structured head-to-head comparison table via Claude Opus.

Inputs: the target business, the resolved competitors, and the full set
of Documents fetched during this analysis. We group docs by who they're
about (target vs. each competitor) and hand the model labeled context,
asking for JSON matching a strict schema. The result is persisted on
Analysis.comparison_json and rendered as a table in the dashboard.
"""

from __future__ import annotations

import json
from typing import Iterable

import anthropic

from ..config import Config
from ..scrapers.base import Competitor

_client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)

# Keep context per group bounded so 5+ competitors still fit comfortably
# inside the Opus 4.7 context window without ballooning cost.
PER_DOC_CHARS = 1500
PER_GROUP_DOCS = 6

ATTRIBUTES: list[dict[str, str]] = [
    {"key": "product_focus", "label": "Product focus"},
    {"key": "pricing", "label": "Pricing"},
    {"key": "target_market", "label": "Target market"},
    {"key": "key_differentiator", "label": "Key differentiator"},
    {"key": "recent_moves", "label": "Recent moves"},
]

_SYSTEM = (
    "You are a competitive intelligence analyst producing a head-to-head "
    "comparison table. For each entity (the target business and each named "
    "competitor), fill in every attribute with a concise phrase (≤ 140 chars) "
    "grounded in the provided excerpts. When the excerpts don't support a "
    'value, use the exact string "unknown" — do not guess.'
)


def _schema(keys: list[str]) -> dict:
    value_props = {k: {"type": "string"} for k in keys}
    return {
        "type": "object",
        "properties": {
            "rows": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "entity": {"type": "string"},
                        "is_target": {"type": "boolean"},
                        "values": {
                            "type": "object",
                            "properties": value_props,
                            "required": list(keys),
                            "additionalProperties": False,
                        },
                    },
                    "required": ["entity", "is_target", "values"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["rows"],
        "additionalProperties": False,
    }


def _group_docs(docs, target_name: str, competitors: list[Competitor]):
    """Return {'<label>': [docs]} grouped by who the doc is about."""

    groups: dict[str, list] = {target_name: []}
    for comp in competitors:
        groups[comp.name] = []

    comp_by_domain = {c.domain: c.name for c in competitors}
    comp_by_name_lower = {c.name.lower(): c.name for c in competitors}
    target_lower = target_name.lower()

    for doc in docs:
        labelled = doc.metadata.get("competitor")
        if labelled and labelled in groups:
            groups[labelled].append(doc)
            continue
        # Fall back to best-effort labeling from URL domain or text content.
        url = doc.metadata.get("source", "")
        for domain, name in comp_by_domain.items():
            if domain in url:
                groups[name].append(doc)
                break
        else:
            text_lower = (doc.page_content or "")[:2000].lower()
            if target_lower and target_lower in text_lower:
                groups[target_name].append(doc)
                continue
            for name_lower, name in comp_by_name_lower.items():
                if name_lower in text_lower:
                    groups[name].append(doc)
                    break
    return groups


def _render_group(label: str, docs: Iterable) -> str:
    lines = [f"=== {label} ==="]
    for doc in list(docs)[:PER_GROUP_DOCS]:
        src = doc.metadata.get("source", "unknown")
        excerpt = (doc.page_content or "")[:PER_DOC_CHARS].strip()
        if not excerpt:
            continue
        lines.append(f"--- {src} ---\n{excerpt}")
    return "\n\n".join(lines)


def generate_comparison(
    target_name: str,
    competitors: list[Competitor],
    docs,
) -> dict | None:
    """Return the comparison dict ({attributes, rows}) or None on failure."""

    if not competitors or not docs:
        return None

    groups = _group_docs(docs, target_name, competitors)
    non_empty = {label: group for label, group in groups.items() if group}
    if target_name not in non_empty and not any(
        c.name in non_empty for c in competitors
    ):
        return None

    context = "\n\n".join(_render_group(label, grp) for label, grp in non_empty.items())
    attributes = ATTRIBUTES
    keys = [a["key"] for a in attributes]
    user = (
        f"Target business: {target_name}\n"
        f"Competitors: {', '.join(c.name for c in competitors)}\n\n"
        "Build a row for the target business and one row per competitor.\n\n"
        f"Labeled source excerpts:\n\n{context}"
    )

    try:
        response = _client.messages.create(
            model=Config.CLAUDE_MODEL,
            max_tokens=4096,
            thinking={"type": "adaptive"},
            system=_SYSTEM,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": _schema(keys)}},
        )
    except Exception:
        return None

    text = next((b.text for b in response.content if b.type == "text"), "").strip()
    try:
        data = json.loads(text)
    except Exception:
        return None

    return {"attributes": attributes, "rows": data.get("rows", [])}
