import asyncio

from ..models import add_edge, upsert_node
from .async_loader import load_documents
from .edge_infer import infer_relation_async
from .entities import extract_entities
from .rag import build_qa_chain
from .source_selection import select_sources


async def process_doc(doc):
    page_url = doc.metadata.get("source", "unknown")
    upsert_node(page_url, "PAGE")

    entities = extract_entities(doc.page_content)
    for ent, ent_type in entities:
        upsert_node(ent, ent_type)
        add_edge(page_url, ent, "mentions")

    tasks = []
    pairs = []
    for i in range(len(entities)):
        for j in range(i + 1, len(entities)):
            ent1, ent2 = entities[i][0], entities[j][0]
            pairs.append((ent1, ent2))
            tasks.append(infer_relation_async(doc.page_content, ent1, ent2))

    relations = await asyncio.gather(*tasks)
    for (ent1, ent2), rel in zip(pairs, relations):
        if rel and rel != "no_relation":
            add_edge(ent1, ent2, rel)


async def run_pipeline_async(question: str):
    urls = select_sources(question)
    docs = await load_documents(urls)
    if not docs:
        return "No data retrieved.", {}

    await asyncio.gather(*[process_doc(doc) for doc in docs])

    chain = build_qa_chain(docs)
    result = chain.invoke({"query": question})
    answer = result["result"].strip()
    details = {
        f"[{i + 1}]": doc.metadata.get("source", "N/A")
        for i, doc in enumerate(result["source_documents"])
    }
    return answer, details


def run_pipeline(question: str):
    return asyncio.run(run_pipeline_async(question))
