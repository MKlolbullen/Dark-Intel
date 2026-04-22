from __future__ import annotations

import asyncio

from langchain_core.documents import Document

from ..scrapers import REGISTRY, Competitor, ScrapedDoc, ScrapeQuery


async def gather_documents(
    business_name: str,
    industry: str,
    question: str,
    channels: list[str],
    competitors: tuple[Competitor, ...] = (),
    limit_per_source: int = 20,
) -> list[Document]:
    """Run every requested scraper in parallel and return LangChain Documents.

    Unknown channel names are silently skipped, as are channels whose scrapers
    are disabled (e.g. Reddit without API creds, LinkedIn without a token).
    """

    query = ScrapeQuery(
        business_name=business_name,
        industry=industry,
        question=question,
        limit_per_source=limit_per_source,
        competitors=competitors,
    )
    scrapers = [REGISTRY[name]() for name in channels if name in REGISTRY]
    results = await asyncio.gather(*[s.fetch(query) for s in scrapers])

    docs: list[Document] = []
    for batch in results:
        for d in batch:
            docs.append(_to_document(d))
    return docs


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
