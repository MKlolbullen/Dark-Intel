from .base import BaseScraper, ScrapedDoc, ScrapeQuery
from .hackernews import HackerNewsScraper
from .linkedin import LinkedInScraper
from .news import NewsScraper
from .reddit import RedditScraper

REGISTRY: dict[str, type[BaseScraper]] = {
    "news": NewsScraper,
    "reddit": RedditScraper,
    "hn": HackerNewsScraper,
    "linkedin": LinkedInScraper,
}

__all__ = [
    "REGISTRY",
    "BaseScraper",
    "ScrapeQuery",
    "ScrapedDoc",
    "HackerNewsScraper",
    "LinkedInScraper",
    "NewsScraper",
    "RedditScraper",
]
