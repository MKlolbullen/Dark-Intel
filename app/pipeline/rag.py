import anthropic
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

from ..config import Config

_anthropic = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)

_SYSTEM = (
    "You are an OSINT analyst. Answer the user's question using only the numbered "
    "context excerpts. Cite the relevant excerpts inline as [1], [2], etc. If the "
    "context does not contain the answer, say so."
)


def _format_context(docs):
    return "\n\n".join(
        f"[{i}] (source: {doc.metadata.get('source', 'unknown')})\n{doc.page_content}"
        for i, doc in enumerate(docs, start=1)
    )


class RagChain:
    """FAISS retrieval (OpenAI embeddings) + answer generation (Anthropic)."""

    def __init__(self, documents):
        embeddings = OpenAIEmbeddings(
            model=Config.EMBEDDING_MODEL,
            api_key=Config.OPENAI_API_KEY,
        )
        self._vectordb = FAISS.from_documents(documents, embeddings)
        self._retriever = self._vectordb.as_retriever(search_kwargs={"k": 6})

    def invoke(self, inputs: dict) -> dict:
        question = inputs["query"]
        source_documents = self._retriever.invoke(question)
        prompt = (
            f"{_format_context(source_documents)}\n\n"
            f"Question: {question}\n\n"
            f"Answer (cite with [n]):"
        )
        response = _anthropic.messages.create(
            model=Config.CLAUDE_MODEL,
            max_tokens=4096,
            thinking={"type": "adaptive"},
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        answer = next(
            (b.text for b in response.content if b.type == "text"), ""
        )
        return {"result": answer.strip(), "source_documents": source_documents}


def build_qa_chain(documents):
    return RagChain(documents)
