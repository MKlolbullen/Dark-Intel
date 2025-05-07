from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate

def build_qa_chain(documents):
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vectordb  = FAISS.from_documents(documents, embeddings)
    retriever = vectordb.as_retriever(search_kwargs={"k": 6})

    prompt = PromptTemplate(
      input_variables=["context", "question"],
      template="{context}\n\nQUESTION: {question}\n\nANSWER (cite with [n]):"
    )
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
    return RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        chain_type_kwargs={"prompt": prompt},
        return_source_documents=True
    )
