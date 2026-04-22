"""Follow-up Q&A over a completed analysis.

Rebuilds a FAISS index from Source.text for the given analysis the first
time it's asked, caches it in-process so subsequent questions on the same
analysis are fast, and feeds retrieved excerpts + the last few chat
turns to Claude Opus. Writes a ChatTurn row per question.
"""

from __future__ import annotations

import json
from collections import OrderedDict

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from ..config import Config
from ..llm import get_default_client
from ..models import (
    Analysis,
    Session,
    add_chat_turn,
    engine,
    list_chat_turns,
    load_analysis_sources,
)

# LRU cache of (analysis_id -> FAISS retriever). Bounded to avoid holding
# too many embeddings in memory at once. FAISS indexes are cheap to rebuild.
_CACHE_SIZE = 8
_faiss_cache: OrderedDict[int, object] = OrderedDict()

_SYSTEM = (
    "You are an OSINT analyst answering follow-up questions about a business "
    "and its competitors using only the numbered context excerpts provided. "
    "Cite excerpts inline as [1], [2], etc. When competitor pages appear in "
    "the context and the question invites comparison, contrast the target "
    "business against each competitor on product, pricing, and positioning. "
    "If the context doesn't cover the question, say so plainly rather than "
    "guess. Answer in clear paragraphs; no preamble."
)

_HISTORY_TURNS = 4
_HISTORY_ANSWER_CHARS = 600


def _retriever_for(analysis_id: int):
    if analysis_id in _faiss_cache:
        _faiss_cache.move_to_end(analysis_id)
        return _faiss_cache[analysis_id]

    sources = load_analysis_sources(analysis_id)
    docs: list[Document] = []
    for s in sources:
        if not s.text:
            continue
        metadata = {"source": s.url, "kind": s.kind}
        if s.competitor:
            metadata["competitor"] = s.competitor
        if s.title:
            metadata["title"] = s.title
        docs.append(Document(page_content=s.text, metadata=metadata))
    if not docs:
        return None

    embeddings = OpenAIEmbeddings(
        model=Config.EMBEDDING_MODEL,
        api_key=Config.OPENAI_API_KEY,
    )
    vectordb = FAISS.from_documents(docs, embeddings)
    retriever = vectordb.as_retriever(search_kwargs={"k": 8})

    _faiss_cache[analysis_id] = retriever
    if len(_faiss_cache) > _CACHE_SIZE:
        _faiss_cache.popitem(last=False)
    return retriever


def invalidate(analysis_id: int) -> None:
    _faiss_cache.pop(analysis_id, None)


def _format_context(docs) -> str:
    return "\n\n".join(
        f"[{i}] (source: {doc.metadata.get('source', 'unknown')}"
        f"{', competitor: ' + doc.metadata['competitor'] if doc.metadata.get('competitor') else ''})\n"
        f"{doc.page_content[:1800]}"
        for i, doc in enumerate(docs, start=1)
    )


def _format_history(analysis_id: int) -> str:
    turns = list_chat_turns(analysis_id, limit=_HISTORY_TURNS)
    if not turns:
        return ""
    lines = ["Prior conversation (for context only):"]
    for t in turns:
        lines.append(f"Q: {t.question}")
        lines.append(f"A: {t.answer[:_HISTORY_ANSWER_CHARS]}")
    return "\n".join(lines)


def answer_followup(analysis_id: int, question: str) -> tuple[str, list[str]]:
    """Answer one follow-up question. Returns (answer, source_urls).

    Raises ValueError if the analysis has no retrievable sources.
    """

    with Session(engine) as s:
        analysis = s.get(Analysis, analysis_id)
    if analysis is None:
        raise ValueError(f"Analysis {analysis_id} not found")

    retriever = _retriever_for(analysis_id)
    if retriever is None:
        raise ValueError(
            f"Analysis {analysis_id} has no scraped source text — "
            "re-run the analysis to populate Source.text."
        )

    retrieved = retriever.invoke(question)
    context = _format_context(retrieved)
    history = _format_history(analysis_id)

    competitors_line = ""
    if analysis.competitors:
        try:
            comps = json.loads(analysis.competitors)
            if comps:
                names = ", ".join(c["name"] for c in comps if c.get("name"))
                if names:
                    competitors_line = f"\nKnown competitors: {names}"
        except Exception:
            pass

    header = (
        f"Target business: {analysis.business_name}\n"
        f"Industry: {analysis.industry}{competitors_line}\n\n"
    )
    user_parts = [header]
    if history:
        user_parts.append(history + "\n")
    user_parts.append(f"Current question: {question}\n\n")
    user_parts.append(f"Context:\n{context}\n\n")
    user_parts.append("Answer (cite with [n]):")
    user = "".join(user_parts)

    answer = get_default_client().complete(
        system=_SYSTEM,
        user=user,
        max_tokens=4096,
        thinking=True,
    ).strip()
    source_urls = [d.metadata.get("source", "") for d in retrieved]
    add_chat_turn(
        analysis_id=analysis_id,
        question=question,
        answer=answer,
        sources_json=json.dumps(source_urls),
    )
    return answer, source_urls
