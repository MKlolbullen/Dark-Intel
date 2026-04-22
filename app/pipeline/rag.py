from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

from ..config import Config
from ..llm import get_default_client

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
    """FAISS retrieval (OpenAI embeddings) + answer generation (active LLM provider)."""

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
        answer = get_default_client().complete(
            system=_SYSTEM,
            user=prompt,
            max_tokens=4096,
            thinking=True,
        )
        return {"result": answer.strip(), "source_documents": source_documents}


def build_qa_chain(documents):
    return RagChain(documents)
