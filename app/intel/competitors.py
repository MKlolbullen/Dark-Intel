"""Discover competitors of a target business via Claude.

Used as a fallback when the user doesn't supply an explicit competitor
list. Returns a list of Competitor(name, domain) ready to feed into
CompetitorsScraper.
"""

from __future__ import annotations

import json
import re

import anthropic

from ..config import Config
from ..scrapers.base import Competitor

_client = anthropic.AsyncAnthropic(api_key=Config.ANTHROPIC_API_KEY)

_SYSTEM = (
    "You are a market analyst. Identify the most relevant direct competitors "
    "of the named business in the named industry. Return real, currently "
    "operating companies and their canonical primary domains (no scheme, no "
    "path; e.g. 'openai.com'). Exclude the business itself. Return strict "
    "JSON only — no prose, no markdown."
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "competitors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "domain": {"type": "string"},
                },
                "required": ["name", "domain"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["competitors"],
    "additionalProperties": False,
}


async def discover_competitors(
    business_name: str,
    industry: str,
    n: int = 5,
) -> list[Competitor]:
    user = f"Business: {business_name}\nIndustry: {industry}\nReturn the top {n}."
    try:
        response = await _client.messages.create(
            model=Config.CLAUDE_MODEL,
            max_tokens=512,
            thinking={"type": "adaptive"},
            system=_SYSTEM,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
        )
    except Exception:
        return []
    text = next((b.text for b in response.content if b.type == "text"), "{}").strip()
    try:
        data = json.loads(text)
    except Exception:
        return []
    out: list[Competitor] = []
    seen: set[str] = set()
    for raw in data.get("competitors", []):
        name = (raw.get("name") or "").strip()
        domain = _normalize_domain(raw.get("domain") or "")
        if not name or not domain or domain in seen:
            continue
        seen.add(domain)
        out.append(Competitor(name=name, domain=domain))
    return out[:n]


def parse_user_competitors(raw: str) -> list[Competitor]:
    """Parse a free-form 'Name (domain.com), Name2 (domain2.com)' string from the form."""

    if not raw:
        return []
    out: list[Competitor] = []
    for chunk in re.split(r"[,;\n]", raw):
        chunk = chunk.strip()
        if not chunk:
            continue
        m = re.match(r"^(.+?)\s*\(([^)]+)\)\s*$", chunk)
        if m:
            name = m.group(1).strip()
            domain = _normalize_domain(m.group(2).strip())
        else:
            # Bare token: treat as both name and domain
            name = chunk
            domain = _normalize_domain(chunk)
        if name and domain:
            out.append(Competitor(name=name, domain=domain))
    return out


_SCHEME_RE = re.compile(r"^https?://", re.IGNORECASE)


def _normalize_domain(raw: str) -> str:
    s = _SCHEME_RE.sub("", raw.strip().lower()).strip("/")
    s = s.split("/", 1)[0]
    if s.startswith("www."):
        s = s[4:]
    return s
