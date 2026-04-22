"""X (Twitter) v2 search via the official API. Requires a paid Basic+ plan."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import httpx

from .base import BaseScraper, ScrapedDoc, ScrapeQuery

X_SEARCH = "https://api.twitter.com/2/tweets/search/recent"


class XScraper(BaseScraper):
    """Recent search of tweets mentioning the business name.

    Free tier is write-only as of 2024; this scraper is silently disabled
    unless X_BEARER_TOKEN (Basic plan, ~$200/month) is configured.
    """

    kind = "x"

    @classmethod
    def enabled(cls) -> bool:
        return bool(os.getenv("X_BEARER_TOKEN"))

    async def _fetch(self, query: ScrapeQuery) -> list[ScrapedDoc]:
        token = os.getenv("X_BEARER_TOKEN")
        params = {
            "query": f'"{query.business_name}" -is:retweet lang:en',
            "max_results": min(max(10, query.limit_per_source), 100),
            "tweet.fields": "created_at,author_id,public_metrics",
        }
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(
                X_SEARCH,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
            if r.status_code != 200:
                return []
        data = r.json().get("data", [])
        return [
            ScrapedDoc(
                text=t.get("text", ""),
                url=f"https://x.com/i/web/status/{t['id']}",
                kind=self.kind,
                author=t.get("author_id"),
                published_at=_parse_ts(t.get("created_at")),
                metadata={"public_metrics": t.get("public_metrics", {})},
            )
            for t in data
            if t.get("text")
        ]


def _parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None
