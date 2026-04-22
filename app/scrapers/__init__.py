from .base import BaseScraper, ScrapedDoc, ScrapeQuery
from .hackernews import HackerNewsScraper
from .linkedin import LinkedInScraper
from .news import NewsScraper
from .reddit import RedditScraper
from .reviews import ReviewsScraper
from .x import XScraper

REGISTRY: dict[str, type[BaseScraper]] = {
    "news": NewsScraper,
    "reddit": RedditScraper,
    "hn": HackerNewsScraper,
    "linkedin": LinkedInScraper,
    "x": XScraper,
    "reviews": ReviewsScraper,
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
    "ReviewsScraper",
    "XScraper",
]
