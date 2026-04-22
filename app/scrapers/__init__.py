from .base import BaseScraper, Competitor, ScrapedDoc, ScrapeQuery
from .competitors import CompetitorsScraper
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
    "competitor": CompetitorsScraper,
}

__all__ = [
    "REGISTRY",
    "BaseScraper",
    "Competitor",
    "ScrapeQuery",
    "ScrapedDoc",
    "CompetitorsScraper",
    "HackerNewsScraper",
    "LinkedInScraper",
    "NewsScraper",
    "RedditScraper",
    "ReviewsScraper",
    "XScraper",
]
