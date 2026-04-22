"""Fetch a curated path set per identified competitor for product / pricing comparison."""

from __future__ import annotations

import asyncio

import httpx
from bs4 import BeautifulSoup

from .base import BaseScraper, Competitor, ScrapedDoc, ScrapeQuery

# Pages most likely to surface product, pricing, positioning, and recent moves.
DEFAULT_PATHS: tuple[str, ...] = (
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
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
CONCURRENCY = 8


class CompetitorsScraper(BaseScraper):
    """For each Competitor in the query, GET a curated path set and clean to text.

    Discovery (when the user didn't supply competitors) happens upstream
    in source_selection.gather_documents; this scraper only fetches.
    """

    kind = "competitor"

    async def _fetch(self, query: ScrapeQuery) -> list[ScrapedDoc]:
        if not query.competitors:
            return []
        sem = asyncio.Semaphore(CONCURRENCY)
        async with httpx.AsyncClient(
            headers=HEADERS, follow_redirects=True, timeout=15
        ) as client:
            tasks = [
                self._fetch_one(sem, client, comp, path)
                for comp in query.competitors
                for path in DEFAULT_PATHS
            ]
            results = await asyncio.gather(*tasks)
        docs = [r for r in results if r is not None]
        # Cap per competitor to keep entity-pair fan-out under control.
        per_competitor = max(1, query.limit_per_source)
        capped: list[ScrapedDoc] = []
        counts: dict[str, int] = {}
        for d in docs:
            key = d.competitor or ""
            if counts.get(key, 0) >= per_competitor:
                continue
            counts[key] = counts.get(key, 0) + 1
            capped.append(d)
        return capped

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
            except Exception:
                return None
        text = _html_to_text(r.text)
        if len(text) < 200:
            return None  # likely a redirect to a JS shell or empty page
        return ScrapedDoc(
            text=text,
            url=url,
            kind=self.kind,
            title=_extract_title(r.text),
            competitor=comp.name,
            metadata={"path": path, "domain": comp.domain},
        )


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    return "\n".join(
        line.strip() for line in soup.get_text("\n").splitlines() if line.strip()
    )


def _extract_title(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return None
