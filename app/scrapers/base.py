from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Competitor:
    """A competitor of the target business, identified by display name + canonical domain."""

    name: str
    domain: str  # e.g. "openai.com" — no scheme, no path


@dataclass(frozen=True)
class ScrapeQuery:
    """A user-supplied intelligence query, threaded through every scraper."""

    business_name: str
    industry: str
    question: str
    limit_per_source: int = 20
    competitors: tuple[Competitor, ...] = ()


@dataclass
class ScrapedDoc:
    """A single document retrieved by a scraper, ready for the pipeline."""

    text: str
    url: str
    kind: str  # one of news / reddit / hn / linkedin / x / reviews / competitor
    title: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    competitor: str | None = None  # set on competitor-channel docs to the competitor's name
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseScraper:
    """Common shape for every source family.

    Subclasses override `kind` and `_fetch`. `enabled()` lets a scraper
    silently no-op when its credentials are missing — pipelines don't
    need to know which channels are configured.
    """

    kind: str = "generic"

    @classmethod
    def enabled(cls) -> bool:
        return True

    async def fetch(self, query: ScrapeQuery) -> list[ScrapedDoc]:
        if not self.enabled():
            return []
        try:
            return await self._fetch(query)
        except Exception:
            # A single source failing must not nuke the whole analysis.
            return []

    async def _fetch(self, query: ScrapeQuery) -> list[ScrapedDoc]:
        raise NotImplementedError
