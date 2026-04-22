"""Trustpilot reviews scraper. ToS-restricted; off by default.

Trustpilot's `/review/<domain>` pages render server-side and are
parseable with plain httpx — for now. Cloudflare will eventually push
back at scale; if that happens, swap `_fetch_html` for a Playwright
implementation. See SCRAPING.md for the legal/ToS context.

Glassdoor and G2 require live Playwright + anti-bot evasion to be
reliable. They're stubbed as `NotImplementedError` until someone takes
on that work.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from .base import BaseScraper, ScrapedDoc, ScrapeQuery

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


class ReviewsScraper(BaseScraper):
    kind = "reviews"

    @classmethod
    def enabled(cls) -> bool:
        return os.getenv("ENABLE_REVIEW_SCRAPERS") == "1"

    async def _fetch(self, query: ScrapeQuery) -> list[ScrapedDoc]:
        domain = _guess_domain(query.business_name)
        if not domain:
            return []
        url = f"https://www.trustpilot.com/review/{domain}"
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=20) as client:
            r = await client.get(url)
            if r.status_code != 200:
                return []
        return list(_parse_reviews(r.text, url, query.limit_per_source))


def _guess_domain(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "", s)
    return f"{s}.com" if s else ""


def _parse_reviews(html: str, page_url: str, limit: int) -> list[ScrapedDoc]:
    soup = BeautifulSoup(html, "html.parser")
    docs: list[ScrapedDoc] = []
    for card in soup.select("article")[:limit]:
        body = card.find("p", attrs={"data-service-review-text-typography": True}) or card.find("p")
        if not body:
            continue
        text = body.get_text(" ", strip=True)
        if not text:
            continue
        author_el = card.find(attrs={"data-consumer-name-typography": True})
        date_el = card.find("time")
        docs.append(
            ScrapedDoc(
                text=text,
                url=page_url,
                kind="reviews",
                author=author_el.get_text(strip=True) if author_el else None,
                published_at=_parse_iso(date_el.get("datetime") if date_el else None),
                metadata={"site": "trustpilot"},
            )
        )
    return docs


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None
