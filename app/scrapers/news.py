from __future__ import annotations

import asyncio
import logging

import httpx

from ._html import (
    clean_html_to_text,
    discover_internal_paths,
    extract_meta_summary,
    extract_title,
)
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

MIN_BODY_CHARS = 200
MIN_META_CHARS = 80


class NewsScraper(BaseScraper):
    """Fetch and clean a curated set of news + own-site URLs.

    For the user's own website (`ScrapeQuery.business_domain`) we fetch
    the homepage first, then parse its navigation for paths whose slug
    matches common nav keywords across several languages. That way
    non-English sites (om-oss, uber-uns, a-propos, sobre, …) aren't
    just an empty bag of 404s.

    When a page's main body collapses to under `MIN_BODY_CHARS` (likely
    a JS-rendered shell), we fall back to the meta summary — title +
    og: / description — so the corpus still gets *something*.
    """

    kind = "news"

    def _industry_seeds(self, query: ScrapeQuery) -> list[str]:
        seeds = list(GENERIC_SEEDS)
        industry = (query.industry or "").lower()
        for key, urls in INDUSTRY_SEEDS.items():
            if key in industry:
                seeds.extend(urls)
        return list(dict.fromkeys(seeds))

    async def _fetch(self, query: ScrapeQuery) -> list[ScrapedDoc]:
        async with httpx.AsyncClient(
            headers=HEADERS, follow_redirects=True, timeout=15
        ) as client:
            tasks: list[asyncio.Future] = []
            for url in self._industry_seeds(query):
                tasks.append(self._fetch_url(client, url))
            own_future = None
            if query.business_domain:
                own_future = asyncio.ensure_future(
                    self._fetch_domain(client, query.business_domain)
                )
            seed_results = await asyncio.gather(*tasks) if tasks else []
        docs = [r for r in seed_results if r is not None]
        if own_future is not None:
            docs.extend(await own_future)
        return docs[: query.limit_per_source]

    async def _fetch_url(
        self, client: httpx.AsyncClient, url: str
    ) -> ScrapedDoc | None:
        try:
            r = await client.get(url)
            r.raise_for_status()
        except Exception as exc:
            logger.info("news GET %s failed: %s", url, exc)
            return None
        return _as_doc(url, r.text, self.kind)

    async def _fetch_domain(
        self, client: httpx.AsyncClient, domain: str
    ) -> list[ScrapedDoc]:
        root_url = f"https://{domain}/"
        try:
            r = await client.get(root_url)
            r.raise_for_status()
        except Exception as exc:
            logger.info("news GET %s failed: %s", root_url, exc)
            return []
        root_html = r.text
        paths = discover_internal_paths(root_html, domain)
        logger.info(
            "news discovered %d nav path(s) on %s: %s",
            len(paths),
            domain,
            paths,
        )

        docs: list[ScrapedDoc] = []
        root_doc = _as_doc(root_url, root_html, self.kind)
        if root_doc:
            docs.append(root_doc)

        tasks = [self._fetch_url(client, f"https://{domain}{p}") for p in paths]
        for result in await asyncio.gather(*tasks):
            if result is not None:
                docs.append(result)
        return docs


def _as_doc(url: str, html: str, kind: str) -> ScrapedDoc | None:
    text = clean_html_to_text(html)
    if len(text) < MIN_BODY_CHARS:
        fallback = extract_meta_summary(html)
        if len(fallback) >= MIN_META_CHARS:
            logger.debug("news %s body thin (%d chars), using meta summary", url, len(text))
            text = fallback
        else:
            logger.debug("news %s too thin (body=%d meta=%d), dropping", url, len(text), len(fallback))
            return None
    return ScrapedDoc(text=text, url=url, kind=kind, title=extract_title(html))
