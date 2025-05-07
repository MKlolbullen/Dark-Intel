def select_sources(q: str) -> list[str]:
    q = q.lower()
    if any(k in q for k in ("competitor", "market", "trend")):
        return [
            "https://techcrunch.com/tag/fintech/",
            "https://www.reuters.com/finance/",
        ]
    return ["https://news.ycombinator.com/"]
