import asyncio
from typing import Sequence

from ..config import Config
from ..models import add_edge, upsert_node
from .edge_infer import infer_relation_async
from .entities import extract_entities
from .rag import build_qa_chain
from .source_selection import gather_documents


async def process_doc(doc):
    page_url = doc.metadata.get("source", "unknown")
    upsert_node(page_url, "PAGE")

    entities = extract_entities(doc.page_content)
    for ent, ent_type in entities:
        upsert_node(ent, ent_type)
        add_edge(page_url, ent, "mentions")

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
            add_edge(ent1, ent2, rel)


async def run_pipeline_async(
    business_name: str,
    industry: str,
    question: str,
    channels: Sequence[str] | None = None,
):
    chans = list(channels) if channels else list(Config.DEFAULT_CHANNELS)
    docs = await gather_documents(business_name, industry, question, chans)
    if not docs:
        return "No data retrieved.", {}

    await asyncio.gather(*[process_doc(doc) for doc in docs])

    chain = build_qa_chain(docs)
    full_question = (
        f"Business: {business_name}\nIndustry: {industry}\n\nQuestion: {question}"
    )
    result = chain.invoke({"query": full_question})
    answer = result["result"].strip()
    details = {
        f"[{i + 1}]": doc.metadata.get("source", "N/A")
        for i, doc in enumerate(result["source_documents"])
    }
    return answer, details


def run_pipeline(
    business_name: str,
    industry: str,
    question: str,
    channels: Sequence[str] | None = None,
):
    return asyncio.run(run_pipeline_async(business_name, industry, question, channels))
