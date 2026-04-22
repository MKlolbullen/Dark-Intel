from __future__ import annotations

import asyncio
import logging

import httpx

from ._html import clean_html_to_text, extract_title
from .base import BaseScraper, ScrapedDoc, ScrapeQuery

logger = logging.getLogger(__name__)

# Real browser UA — Reuters and others 401 on generic bot UAs.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Industry seed pages. Keys are lowercased substrings of the industry input.
# Generic seeds are appended for every query so we always have something to fetch.
INDUSTRY_SEEDS: dict[str, list[str]] = {
    "fintech": [
        "https://techcrunch.com/category/fintech/",
        "https://www.reuters.com/finance/",
    ],
    "ai": [
        "https://techcrunch.com/category/artificial-intelligence/",
        "https://www.reuters.com/technology/artificial-intelligence/",
    ],
    "saas": ["https://techcrunch.com/category/enterprise/"],
    "healthcare": ["https://www.reuters.com/business/healthcare-pharmaceuticals/"],
    "energy": ["https://www.reuters.com/business/energy/"],
    "retail": ["https://www.reuters.com/business/retail-consumer/"],
}
GENERIC_SEEDS = [
    "https://techcrunch.com/",
]

# When the user supplies their own website, fetch the same curated path set
# we use for competitor domains so their own about / pricing / products text
# lands in the corpus alongside.
OWN_SITE_PATHS: tuple[str, ...] = (
    "/",
    "/about",
    "/about-us",
    "/product",
    "/products",
    "/features",
    "/pricing",
    "/blog",
    "/news",
)


class NewsScraper(BaseScraper):
    """Fetch and clean a curated set of news + own-site URLs.

    Lower-friction than the structured news APIs: just GET each seed and
    let the entity extraction + RAG layers do the rest. Also pulls the
    user's own website paths when `ScrapeQuery.business_domain` is set —
    prefer that over the old `{slug}.com/about` guess, which was almost
    always a 404.
    """

    kind = "news"

    def _seeds(self, query: ScrapeQuery) -> list[str]:
        seeds = list(GENERIC_SEEDS)
        industry = (query.industry or "").lower()
        for key, urls in INDUSTRY_SEEDS.items():
            if key in industry:
                seeds.extend(urls)
        if query.business_domain:
            for path in OWN_SITE_PATHS:
                seeds.append(f"https://{query.business_domain}{path}")
        return list(dict.fromkeys(seeds))  # dedupe, preserve order

    async def _fetch(self, query: ScrapeQuery) -> list[ScrapedDoc]:
        urls = self._seeds(query)
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15) as client:
            results = await asyncio.gather(*[self._get(client, u) for u in urls])
        docs = [r for r in results if r is not None]
        return docs[: query.limit_per_source]

    async def _get(self, client: httpx.AsyncClient, url: str) -> ScrapedDoc | None:
        try:
            r = await client.get(url)
            r.raise_for_status()
        except Exception as exc:
            logger.info("news GET %s failed: %s", url, exc)
            return None
        text = clean_html_to_text(r.text)
        if len(text) < 200:
            logger.debug("news GET %s returned only %d chars, dropping", url, len(text))
            return None
        return ScrapedDoc(
            text=text,
            url=url,
            kind=self.kind,
            title=extract_title(r.text),
        )
