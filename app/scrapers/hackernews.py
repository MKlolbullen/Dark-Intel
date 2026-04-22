from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import httpx

from .base import BaseScraper, ScrapedDoc, ScrapeQuery

logger = logging.getLogger(__name__)

HN_SEARCH = "https://hn.algolia.com/api/v1/search"


class HackerNewsScraper(BaseScraper):
    """Algolia-powered Hacker News search. No auth required.

    HN's full-text search matches anything containing the query string
    (e.g. `ica` matches silica, medical, etc.). We filter client-side to
    docs where the business name appears at word boundaries in the title
    or body — this drops the long tail of unrelated hits that otherwise
    flood entity extraction with junk.
    """

    kind = "hn"

    async def _fetch(self, query: ScrapeQuery) -> list[ScrapedDoc]:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                HN_SEARCH,
                params={
                    "query": query.business_name,
                    "tags": "(story,comment)",
                    # Fetch more than we need; the relevance filter below drops many.
                    "hitsPerPage": max(query.limit_per_source * 3, 30),
                },
            )
            r.raise_for_status()
        hits = r.json().get("hits", [])
        pattern = _relevance_pattern(query.business_name)

        kept = 0
        skipped = 0
        docs: list[ScrapedDoc] = []
        for hit in hits:
            text = hit.get("story_text") or hit.get("comment_text") or hit.get("title") or ""
            if not text:
                continue
            title = hit.get("title") or ""
            if pattern is not None and not (pattern.search(text) or pattern.search(title)):
                skipped += 1
                continue
            docs.append(
                ScrapedDoc(
                    text=text,
                    url=hit.get("url") or f"https://news.ycombinator.com/item?id={hit['objectID']}",
                    kind=self.kind,
                    title=title or None,
                    author=hit.get("author"),
                    published_at=_parse_ts(hit.get("created_at_i")),
                    metadata={"points": hit.get("points"), "object_id": hit.get("objectID")},
                )
            )
            kept += 1
            if kept >= query.limit_per_source:
                break
        if skipped:
            logger.info("hn dropped %d irrelevant hits (no word-boundary match)", skipped)
        return docs


def _relevance_pattern(business_name: str) -> re.Pattern | None:
    token = (business_name or "").strip()
    if not token:
        return None
    return re.compile(r"\b" + re.escape(token) + r"\b", re.IGNORECASE)


def _parse_ts(epoch: int | None) -> datetime | None:
    if epoch is None:
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc)
