from __future__ import annotations

import asyncio
import logging

from langchain_core.documents import Document

from ..scrapers import REGISTRY, Competitor, ScrapedDoc, ScrapeQuery

logger = logging.getLogger(__name__)


async def gather_documents(
    business_name: str,
    industry: str,
    question: str,
    channels: list[str],
    competitors: tuple[Competitor, ...] = (),
    limit_per_source: int = 20,
) -> tuple[list[Document], dict[str, int]]:
    """Run every requested scraper in parallel.

    Returns (documents, per_channel_counts). Channel counts include only
    scrapers that actually ran — unknown names and disabled-at-call-time
    scrapers report 0. Exceptions inside scrapers are already swallowed
    by `BaseScraper.fetch` and logged there.
    """

    query = ScrapeQuery(
        business_name=business_name,
        industry=industry,
        question=question,
        limit_per_source=limit_per_source,
        competitors=competitors,
    )
    names = [name for name in channels if name in REGISTRY]
    scrapers = [REGISTRY[name]() for name in names]
    results = await asyncio.gather(*[s.fetch(query) for s in scrapers])

    docs: list[Document] = []
    counts: dict[str, int] = {name: 0 for name in names}
    for name, batch in zip(names, results):
        counts[name] = len(batch)
        for d in batch:
            docs.append(_to_document(d))
    logger.info("scraping finished, docs=%d, counts=%s", len(docs), counts)
    return docs, counts


def _to_document(d: ScrapedDoc) -> Document:
    metadata: dict = {"source": d.url, "kind": d.kind}
    if d.title:
        metadata["title"] = d.title
    if d.author:
        metadata["author"] = d.author
    if d.published_at:
        metadata["published_at"] = d.published_at.isoformat()
    if d.competitor:
        metadata["competitor"] = d.competitor
    metadata.update(d.metadata)
    return Document(page_content=d.text, metadata=metadata)
