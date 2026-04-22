"""Fetch each identified competitor's own website.

Per competitor, fetch the homepage first, parse its navigation for
paths whose slug matches common nav keywords across several languages
(see `_html.NAV_KEYWORDS`), and then fetch those. Same fallback to
meta summary as `news.py` so JS-only shells still contribute.
"""

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
from .base import BaseScraper, Competitor, ScrapedDoc, ScrapeQuery

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
CONCURRENCY = 8
MIN_BODY_CHARS = 200
MIN_META_CHARS = 80


class CompetitorsScraper(BaseScraper):
    kind = "competitor"

    async def _fetch(self, query: ScrapeQuery) -> list[ScrapedDoc]:
        if not query.competitors:
            return []
        sem = asyncio.Semaphore(CONCURRENCY)
        async with httpx.AsyncClient(
            headers=HEADERS, follow_redirects=True, timeout=15
        ) as client:
            groups = await asyncio.gather(*[
                self._scrape_domain(sem, client, comp) for comp in query.competitors
            ])
        # Cap per competitor to keep entity-pair fan-out under control.
        per_competitor = max(1, query.limit_per_source)
        out: list[ScrapedDoc] = []
        for docs in groups:
            out.extend(docs[:per_competitor])
        return out

    async def _scrape_domain(
        self,
        sem: asyncio.Semaphore,
        client: httpx.AsyncClient,
        comp: Competitor,
    ) -> list[ScrapedDoc]:
        root_url = f"https://{comp.domain}/"
        async with sem:
            try:
                r = await client.get(root_url)
                r.raise_for_status()
            except Exception as exc:
                logger.info("competitor GET %s failed: %s", root_url, exc)
                return []
        root_html = r.text
        paths = discover_internal_paths(root_html, comp.domain)
        logger.info(
            "competitor %s: discovered %d nav path(s): %s",
            comp.domain,
            len(paths),
            paths,
        )

        docs: list[ScrapedDoc] = []
        root_doc = _as_competitor_doc(root_url, root_html, comp, "/")
        if root_doc:
            docs.append(root_doc)

        tasks = [
            self._fetch_one(sem, client, comp, path) for path in paths
        ]
        for result in await asyncio.gather(*tasks):
            if result is not None:
                docs.append(result)
        return docs

    async def _fetch_one(
        self,
        sem: asyncio.Semaphore,
        client: httpx.AsyncClient,
        comp: Competitor,
        path: str,
    ) -> ScrapedDoc | None:
        url = f"https://{comp.domain}{path}"
        async with sem:
            try:
                r = await client.get(url)
                r.raise_for_status()
            except Exception as exc:
                logger.debug("competitor GET %s failed: %s", url, exc)
                return None
        return _as_competitor_doc(url, r.text, comp, path)


def _as_competitor_doc(
    url: str, html: str, comp: Competitor, path: str
) -> ScrapedDoc | None:
    text = clean_html_to_text(html)
    if len(text) < MIN_BODY_CHARS:
        fallback = extract_meta_summary(html)
        if len(fallback) >= MIN_META_CHARS:
            logger.info(
                "competitor %s body thin (%d chars), using meta summary",
                url,
                len(text),
            )
            text = fallback
        else:
            logger.info(
                "competitor GET %s returned only %d chars (likely JS shell), dropping",
                url,
                len(text),
            )
            return None
    return ScrapedDoc(
        text=text,
        url=url,
        kind="competitor",
        title=extract_title(html),
        competitor=comp.name,
        metadata={"path": path, "domain": comp.domain},
    )
