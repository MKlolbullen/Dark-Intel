import asyncio

import httpx
from bs4 import BeautifulSoup
from langchain_core.documents import Document

HEADERS = {"User-Agent": "intel-bot/0.2"}


async def _get(url, client):
    try:
        r = await client.get(url, timeout=15)
        r.raise_for_status()
        return url, r.text
    except Exception:
        return url, ""


async def fetch_many(urls):
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as c:
        results = await asyncio.gather(*[_get(u, c) for u in urls])
    return {u: html for u, html in results if html}


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return "\n".join(
        line.strip() for line in soup.get_text("\n").splitlines() if line.strip()
    )


async def load_documents(urls):
    htmls = await fetch_many(urls)
    return [
        Document(page_content=_html_to_text(html), metadata={"source": url})
        for url, html in htmls.items()
    ]
