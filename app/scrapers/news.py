from __future__ import annotations

import asyncio

import httpx
from bs4 import BeautifulSoup

from .base import BaseScraper, ScrapedDoc, ScrapeQuery

HEADERS = {"User-Agent": "dark-intel/0.2 (+https://github.com/MKlolbullen/Dark-Intel)"}

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
    "https://www.reuters.com/",
    "https://techcrunch.com/",
]


class NewsScraper(BaseScraper):
    """Fetch and clean a curated set of news / company-page URLs.

    Lower-friction than the structured news APIs: just GET each seed and
    let the entity extraction + RAG layers do the rest.
    """

    kind = "news"

    def _seeds(self, query: ScrapeQuery) -> list[str]:
        seeds = list(GENERIC_SEEDS)
        industry = (query.industry or "").lower()
        for key, urls in INDUSTRY_SEEDS.items():
            if key in industry:
                seeds.extend(urls)
        # Best-effort company about page; harmless if it 404s.
        slug = query.business_name.strip().lower().replace(" ", "")
        if slug:
            seeds.append(f"https://{slug}.com/about")
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
        except Exception:
            return None
        return ScrapedDoc(
            text=_html_to_text(r.text),
            url=url,
            kind=self.kind,
            title=_extract_title(r.text),
        )


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return "\n".join(
        line.strip() for line in soup.get_text("\n").splitlines() if line.strip()
    )


def _extract_title(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return None
