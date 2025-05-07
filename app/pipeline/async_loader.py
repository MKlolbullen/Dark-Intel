import asyncio, httpx
from langchain_community.document_loaders import WebBaseLoader

HEADERS = {"User-Agent": "intel-bot/0.2"}

async def _get(u, client):
    try:
        r = await client.get(u, timeout=15)
        r.raise_for_status(); return u, r.text
    except Exception: return u, ""

async def fetch_many(urls):
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as c:
        res = await asyncio.gather(*[_get(u, c) for u in urls])
    return {u: h for u, h in res if h}

def load_documents(urls):
    htmls = asyncio.run(fetch_many(urls))
    docs = []
    for url, html in htmls.items():
        docs.extend(WebBaseLoader.from_html(html, url=url).load())
    return docs
