import asyncio
import json
from typing import Sequence

from ..config import Config
from ..analysis.comparison import generate_comparison
from ..intel.competitors import discover_competitors, parse_user_competitors
from ..models import (
    add_edge,
    add_mention,
    create_analysis,
    update_analysis_comparison,
    update_analysis_summary,
    upsert_node,
    upsert_source,
)
from ..scrapers import Competitor
from .edge_infer import infer_relation_async
from .entities import extract_entities
from .rag import build_qa_chain
from .source_selection import gather_documents


def _snippet_for(text: str, entity: str, span: int = 160) -> str:
    idx = text.lower().find(entity.lower())
    if idx < 0:
        return text[:span]
    start = max(0, idx - span // 2)
    return text[start : start + span]


async def process_doc(doc, analysis_id: int):
    page_url = doc.metadata.get("source", "unknown")
    kind = doc.metadata.get("kind", "news")
    competitor = doc.metadata.get("competitor")
    upsert_node(page_url, "PAGE")
    source_id = upsert_source(
        url=page_url,
        kind=kind,
        scraper=kind,
        title=doc.metadata.get("title"),
        competitor=competitor,
    )

    entities = extract_entities(doc.page_content)
    for ent, ent_type in entities:
        node_id = upsert_node(ent, ent_type)
        add_edge(page_url, ent, "mentions", analysis_id=analysis_id)
        add_mention(
            analysis_id=analysis_id,
            source_id=source_id,
            node_id=node_id,
            snippet=_snippet_for(doc.page_content, ent),
        )

    pairs = []
    tasks = []
    for i in range(len(entities)):
        for j in range(i + 1, len(entities)):
            ent1, ent2 = entities[i][0], entities[j][0]
            pairs.append((ent1, ent2))
            tasks.append(infer_relation_async(doc.page_content, ent1, ent2))

    relations = await asyncio.gather(*tasks)
    for (ent1, ent2), rel in zip(pairs, relations):
        if rel and rel != "no_relation":
            add_edge(ent1, ent2, rel, analysis_id=analysis_id)


async def _resolve_competitors(
    business_name: str,
    industry: str,
    channels: list[str],
    user_supplied: str,
) -> tuple[Competitor, ...]:
    """Use user-supplied competitors if provided; otherwise auto-discover when relevant."""

    explicit = parse_user_competitors(user_supplied)
    if explicit:
        return tuple(explicit)
    if "competitor" not in channels or not business_name:
        return ()
    return tuple(await discover_competitors(business_name, industry))


async def run_pipeline_async(
    business_name: str,
    industry: str,
    question: str,
    channels: Sequence[str] | None = None,
    competitors_input: str = "",
):
    chans = list(channels) if channels else list(Config.DEFAULT_CHANNELS)
    competitors = await _resolve_competitors(business_name, industry, chans, competitors_input)

    competitors_json = (
        json.dumps([{"name": c.name, "domain": c.domain} for c in competitors])
        if competitors
        else None
    )
    analysis_id = create_analysis(
        business_name=business_name,
        industry=industry,
        question=question,
        model=Config.CLAUDE_MODEL,
        competitors_json=competitors_json,
    )

    docs = await gather_documents(
        business_name, industry, question, chans, competitors=competitors
    )
    if not docs:
        update_analysis_summary(analysis_id, "No data retrieved.")
        return analysis_id, "No data retrieved.", {}

    await asyncio.gather(*[process_doc(doc, analysis_id) for doc in docs])

    chain = build_qa_chain(docs)
    competitors_line = (
        f"\nCompetitors: {', '.join(c.name for c in competitors)}" if competitors else ""
    )
    full_question = (
        f"Business: {business_name}\nIndustry: {industry}{competitors_line}\n\n"
        f"Question: {question}\n\n"
        "When competitor websites are present in the context, contrast the target "
        "business against each competitor on product, pricing, and positioning where "
        "the evidence supports it. Cite the competitor by name."
    )
    result = chain.invoke({"query": full_question})
    answer = result["result"].strip()
    details = {
        f"[{i + 1}]": doc.metadata.get("source", "N/A")
        for i, doc in enumerate(result["source_documents"])
    }
    update_analysis_summary(analysis_id, answer)

    if competitors:
        comparison = generate_comparison(business_name, list(competitors), docs)
        if comparison:
            update_analysis_comparison(analysis_id, json.dumps(comparison))

    return analysis_id, answer, details


def run_pipeline(
    business_name: str,
    industry: str,
    question: str,
    channels: Sequence[str] | None = None,
    competitors_input: str = "",
):
    return asyncio.run(
        run_pipeline_async(business_name, industry, question, channels, competitors_input)
    )
