import asyncio
from .source_selection import select_sources
from .async_loader import load_documents
from .rag import build_qa_chain
from .entities import extract_entities
from .edge_infer import infer_relation_async
from ..models import add_edge, upsert_node

async def process_doc(doc):
    """Async process a single Document: extract entities, build graph edges."""
    page_url = doc.metadata.get("source", "unknown")
    upsert_node(page_url, "PAGE")

    entities = extract_entities(doc.page_content)
    for ent, ent_type in entities:
        upsert_node(ent, ent_type)
        add_edge(page_url, ent, "mentions")

    # Infer relations concurrently between entity pairs
    tasks = []
    for i in range(len(entities)):
        for j in range(i + 1, len(entities)):
            ent1, ent2 = entities[i][0], entities[j][0]
            tasks.append(infer_relation_async(doc.page_content, ent1, ent2))

    # Wait for all inference
    relations = await asyncio.gather(*tasks)
    edges = []
    idx = 0
    for i in range(len(entities)):
        for j in range(i + 1, len(entities)):
            rel = relations[idx]
            if rel and rel != "no_relation":
                edges.append((entities[i][0], entities[j][0], rel))
            idx += 1

    for src, tgt, rel in edges:
        add_edge(src, tgt, rel)

async def run_pipeline_async(question: str):
    urls = select_sources(question)
    docs = load_documents(urls)
    if not docs:
        return "No data retrieved.", {}

    # Async enrich all docs
    await asyncio.gather(*[process_doc(doc) for doc in docs])

    # Run RAG LLM pipeline
    chain = build_qa_chain(docs)
    result = chain({"query": question})
    answer = result["result"].strip()
    details = {f"[{i+1}]": doc.metadata.get("source", "N/A")
               for i, doc in enumerate(result["source_documents"])}
    return answer, details

# sync wrapper for Flask
def run_pipeline(question: str):
    return asyncio.run(run_pipeline_async(question))
