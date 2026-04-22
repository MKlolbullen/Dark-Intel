from __future__ import annotations

import re
from datetime import datetime, timezone

import httpx

from ..config import Config
from .base import BaseScraper, ScrapedDoc, ScrapeQuery

LINKEDIN_API = "https://api.linkedin.com/v2"
API_VERSION = "202404"


class LinkedInScraper(BaseScraper):
    """LinkedIn REST API v2 — official, OAuth bearer token.

    What this can read with a standard developer token:
      * Org metadata via vanityName lookup (the slug from a /company/<slug> URL)
      * The org's own posts, IF the access token has r_organization_social
        and the token's user is an admin of that org.

    What this CANNOT read without LinkedIn Marketing Developer Platform
    approval (weeks/months of manual review):
      * Search across LinkedIn for mentions of an arbitrary company
      * Posts on orgs the token holder doesn't admin
      * User profiles other than the token owner

    This module covers the official-API surface that's reachable today.
    Anything richer needs MDP — swap `_search` for the Vetted API call.
    """

    kind = "linkedin"

    @classmethod
    def enabled(cls) -> bool:
        return bool(Config.LINKEDIN_ACCESS_TOKEN)

    async def _fetch(self, query: ScrapeQuery) -> list[ScrapedDoc]:
        slug = _slugify(query.business_name)
        if not slug:
            return []
        async with httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {Config.LINKEDIN_ACCESS_TOKEN}",
                "X-Restli-Protocol-Version": "2.0.0",
                "LinkedIn-Version": API_VERSION,
            },
            timeout=20,
        ) as client:
            org = await self._lookup_org(client, slug)
            if not org:
                return []
            return await self._org_posts(client, org, query)

    async def _lookup_org(self, client: httpx.AsyncClient, slug: str) -> dict | None:
        r = await client.get(
            f"{LINKEDIN_API}/organizations",
            params={"q": "vanityName", "vanityName": slug},
        )
        if r.status_code != 200:
            return None
        elements = r.json().get("elements", [])
        return elements[0] if elements else None

    async def _org_posts(
        self,
        client: httpx.AsyncClient,
        org: dict,
        query: ScrapeQuery,
    ) -> list[ScrapedDoc]:
        org_id = org.get("id")
        if not org_id:
            return []
        author_urn = f"urn:li:organization:{org_id}"
        r = await client.get(
            f"{LINKEDIN_API}/posts",
            params={"author": author_urn, "q": "author", "count": query.limit_per_source},
        )
        if r.status_code != 200:
            return []
        elements = r.json().get("elements", [])
        org_url = f"https://www.linkedin.com/company/{org.get('vanityName', '')}"
        docs: list[ScrapedDoc] = []
        for post in elements:
            text = (post.get("commentary") or "").strip()
            if not text:
                continue
            urn = post.get("id", "")
            docs.append(
                ScrapedDoc(
                    text=text,
                    url=f"{org_url}/posts/{urn}" if urn else org_url,
                    kind=self.kind,
                    author=org.get("localizedName"),
                    published_at=_parse_ts(post.get("publishedAt")),
                    metadata={"org_id": org_id, "urn": urn, "lifecycle": post.get("lifecycleState")},
                )
            )
        return docs


def _slugify(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def _parse_ts(ms: int | None) -> datetime | None:
    if not ms:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
