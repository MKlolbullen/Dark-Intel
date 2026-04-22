from __future__ import annotations

from datetime import datetime, timezone

from ..config import Config
from .base import BaseScraper, ScrapedDoc, ScrapeQuery

INDUSTRY_SUBS: dict[str, list[str]] = {
    "fintech": ["fintech", "finance", "Banking"],
    "ai": ["artificial", "MachineLearning", "OpenAI", "ClaudeAI"],
    "saas": ["SaaS", "startups", "Entrepreneur"],
    "healthcare": ["healthIT", "medicine"],
    "energy": ["energy", "RenewableEnergy"],
    "retail": ["retail", "ecommerce"],
}


class RedditScraper(BaseScraper):
    """Async Reddit search via asyncpraw. Disabled if creds are missing."""

    kind = "reddit"

    @classmethod
    def enabled(cls) -> bool:
        return bool(Config.REDDIT_CLIENT_ID and Config.REDDIT_CLIENT_SECRET)

    async def _fetch(self, query: ScrapeQuery) -> list[ScrapedDoc]:
        try:
            import asyncpraw  # imported lazily so the dep stays optional
        except ImportError:
            return []

        reddit = asyncpraw.Reddit(
            client_id=Config.REDDIT_CLIENT_ID,
            client_secret=Config.REDDIT_CLIENT_SECRET,
            user_agent=Config.REDDIT_USER_AGENT,
        )
        try:
            docs = await self._search(reddit, query)
        finally:
            await reddit.close()
        return docs

    async def _search(self, reddit, query: ScrapeQuery) -> list[ScrapedDoc]:
        targets = ["all"]
        industry = (query.industry or "").lower()
        for key, subs in INDUSTRY_SUBS.items():
            if key in industry:
                targets.extend(subs)

        per_target = max(1, query.limit_per_source // len(targets))
        docs: list[ScrapedDoc] = []
        for sub_name in dict.fromkeys(targets):  # dedupe, preserve order
            sub = await reddit.subreddit(sub_name)
            async for submission in sub.search(query.business_name, limit=per_target, sort="new"):
                text = (submission.selftext or submission.title or "").strip()
                if not text:
                    continue
                docs.append(
                    ScrapedDoc(
                        text=text,
                        url=f"https://www.reddit.com{submission.permalink}",
                        kind=self.kind,
                        title=submission.title,
                        author=str(submission.author) if submission.author else None,
                        published_at=datetime.fromtimestamp(submission.created_utc, tz=timezone.utc),
                        metadata={
                            "subreddit": sub_name,
                            "score": submission.score,
                            "num_comments": submission.num_comments,
                        },
                    )
                )
        return docs[: query.limit_per_source]
