from __future__ import annotations

from datetime import datetime, timezone

import httpx

from .base import BaseScraper, ScrapedDoc, ScrapeQuery

HN_SEARCH = "https://hn.algolia.com/api/v1/search"


class HackerNewsScraper(BaseScraper):
    """Algolia-powered Hacker News search. No auth required."""

    kind = "hn"

    async def _fetch(self, query: ScrapeQuery) -> list[ScrapedDoc]:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                HN_SEARCH,
                params={
                    "query": query.business_name,
                    "tags": "(story,comment)",
                    "hitsPerPage": query.limit_per_source,
                },
            )
            r.raise_for_status()
        hits = r.json().get("hits", [])
        docs: list[ScrapedDoc] = []
        for hit in hits:
            text = hit.get("story_text") or hit.get("comment_text") or hit.get("title") or ""
            if not text:
                continue
            docs.append(
                ScrapedDoc(
                    text=text,
                    url=hit.get("url") or f"https://news.ycombinator.com/item?id={hit['objectID']}",
                    kind=self.kind,
                    title=hit.get("title"),
                    author=hit.get("author"),
                    published_at=_parse_ts(hit.get("created_at_i")),
                    metadata={"points": hit.get("points"), "object_id": hit.get("objectID")},
                )
            )
        return docs


def _parse_ts(epoch: int | None) -> datetime | None:
    if epoch is None:
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc)
