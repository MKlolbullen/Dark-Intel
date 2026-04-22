# Scraping Notes

This document covers the legal, ToS, and operational caveats for each source channel. Read it before enabling the opt-in scrapers (`reviews`, `x`).

## Channel summary

| Channel    | Module                          | Auth                                | Default | Notes |
|------------|---------------------------------|-------------------------------------|---------|-------|
| `news`     | `app/scrapers/news.py`          | none                                | on      | Public pages; respect each site's robots.txt at scale. |
| `hn`       | `app/scrapers/hackernews.py`    | none                                | on      | Algolia HN search API. No auth, fair use. |
| `reddit`   | `app/scrapers/reddit.py`        | `REDDIT_CLIENT_ID/SECRET`           | on*     | Official Reddit API via asyncpraw. *On only when creds are present. |
| `linkedin` | `app/scrapers/linkedin.py`      | `LINKEDIN_ACCESS_TOKEN`             | off*    | Official LinkedIn REST API v2. Limited surface without Marketing Developer Platform approval. |
| `x`        | `app/scrapers/x.py`             | `X_BEARER_TOKEN` (paid)             | off     | Official X API v2; requires Basic plan (~$200/mo) for read access. |
| `reviews`  | `app/scrapers/reviews.py`       | `ENABLE_REVIEW_SCRAPERS=1`          | off     | Trustpilot scraping. ToS-restricted, see below. |

`*` "on when creds present" — the channel auto-disables if its env vars aren't set, so checking the box in the UI is a no-op.

## ToS / legal posture per channel

- **News and HN.** No agreement violated; just keep request rates polite.
- **Reddit.** Use of the official API obligates you to follow Reddit's [Data API Terms](https://www.redditinc.com/policies/data-api-terms). The included scraper makes ordinary read calls.
- **LinkedIn.** Uses the official REST API — compliant by construction. The catch is what the API actually exposes:
  - Reachable today with a standard developer token: `vanityName` lookup of an organization, and that organization's own posts (requires `r_organization_social` scope and admin role on the org).
  - Not reachable without LinkedIn Marketing Developer Platform approval (multi-week manual review): cross-platform mention search, posts on orgs you don't admin, third-party profile data.
- **X / Twitter.** The included scraper hits `/2/tweets/search/recent`, which requires a Basic ($200/mo) or higher subscription. Free tier is write-only.
- **Reviews (Trustpilot).** Trustpilot's [Terms of Service](https://legal.trustpilot.com/end-user-terms-and-conditions) prohibit automated scraping. Enabling this channel is **your** decision and exposes you to:
  - IP/account blocks from Trustpilot or its CDN (Cloudflare).
  - Potential C&D / breach-of-contract exposure under their ToS.
  - Reputational risk if your scraping pattern becomes visible.
  Off by default. Set `ENABLE_REVIEW_SCRAPERS=1` to opt in.

## Glassdoor and G2

Both are intentionally **not implemented**. They block automated traffic aggressively, their ToS forbid scraping, and a working scraper would need:

- Headless Chromium with realistic fingerprinting (Playwright + stealth plugin).
- Rotating residential proxies.
- Active maintenance against frequent anti-bot updates.

If you want one anyway, follow the `reviews.py` shape, gate it behind its own opt-in env var, and add a row above. Don't enable it for any production analysis without legal review.

## Operational guidelines

- Keep `ScrapeQuery.limit_per_source` low (default 20) and run analyses sparingly. The graph and dashboard use per-document mention counts, so 20 docs × 8 entities is already 160 LLM-classified pairs per source.
- The `BaseScraper.fetch` swallows per-scraper exceptions deliberately — one site going down or rate-limiting won't kill the whole run, but it also means a silently-broken scraper looks identical to a no-results scraper. Watch the dashboard's source mix; if a channel never appears, run that scraper standalone to debug.
- Sentiment scoring uses Claude Haiku (`CLAUDE_MODEL_RELATION`) with a max of 200 mentions per dashboard load. Past that, increase `MAX_PER_RUN` in `app/analysis/sentiment.py` — but expect the cost.
