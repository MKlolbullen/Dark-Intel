from .source_selection import select_sources
from .async_loader import load_documents
from .rag import build_qa_chain
from .entities import extract_entities
from ..models import add_edge, upsert_node

def run_pipeline(question: str):
    urls = select_sources(question)
    docs = load_documents(urls)
    if not docs:
        return "No data retrieved.", {}

    # Entity graph build
    for d in docs:
        page = d.metadata["source"]
        upsert_node(page, "PAGE")
        for ent, etype in extract_entities(d.page_content):
            add_edge(page, ent, "mentions")
            upsert_node(ent, etype)

    chain = build_qa_chain(docs)
    res = chain({"query": question})
    answer = res["result"].strip()
    details = {f"[{i+1}]": doc.metadata["source"]
               for i, doc in enumerate(res["source_documents"])}
    return answer, details
