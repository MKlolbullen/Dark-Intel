"""Shared HTML → text cleaning + nav discovery + meta fallback.

`clean_html_to_text` drops global page chrome before entity extraction.
`discover_internal_paths` parses a homepage's links to find the real
navigation for that site — works across locales (Swedish /om-oss,
German /uber-uns, French /a-propos, Spanish /sobre, etc.) instead of
guessing fixed English paths.
`extract_meta_summary` pulls title + meta descriptions from a page so
JS-rendered SPAs contribute *something* instead of dropping to zero.
"""

from __future__ import annotations

from urllib.parse import urlparse

from bs4 import BeautifulSoup

NOISE_SELECTORS = (
    "script",
    "style",
    "noscript",
    "svg",
    "nav",
    "header",
    "footer",
    "aside",
    "form",
    "iframe",
    "[role=navigation]",
    "[role=banner]",
    "[role=contentinfo]",
    "[aria-hidden=true]",
)

# Slugs that typically lead to the most useful positioning / product /
# pricing content. English plus common translations for the markets
# we're most likely to hit.
NAV_KEYWORDS: frozenset[str] = frozenset({
    # English
    "about", "about-us", "company", "who-we-are", "our-story", "mission", "team",
    "product", "products", "features", "service", "services", "platform", "solution", "solutions", "offerings",
    "pricing", "plans", "price",
    "news", "blog", "newsroom", "press", "insights", "resources", "articles",
    "customers", "case-studies",
    # Swedish
    "om", "om-oss", "om-foretaget", "foretaget", "tjanster", "vara-tjanster",
    "produkter", "priser", "aktuellt", "nyheter", "pressrum",
    # German
    "ueber-uns", "uber-uns", "ueber", "uber", "unternehmen", "produkte", "preise",
    "leistungen", "nachrichten", "presse",
    # French
    "a-propos", "apropos", "notre-histoire", "produits", "services", "tarifs",
    "actualites", "presse", "nos-services", "entreprise",
    # Spanish
    "sobre", "acerca", "nosotros", "empresa", "productos", "precios", "servicios",
    "noticias", "prensa",
    # Italian
    "chi-siamo", "prodotti", "prezzi", "servizi", "notizie",
    # Dutch
    "over-ons", "over", "diensten", "prijzen", "nieuws",
})

# Max paths to return from discovery. We add root separately.
DEFAULT_DISCOVERY_LIMIT = 10


def clean_html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for selector in NOISE_SELECTORS:
        for tag in soup.select(selector):
            tag.decompose()
    main = soup.find("article") or soup.find("main")
    target = main if main else soup
    return "\n".join(
        line.strip() for line in target.get_text("\n").splitlines() if line.strip()
    )


def extract_title(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return None


def extract_meta_summary(html: str) -> str:
    """Title + og:/meta descriptions, deduped. Useful when the body is
    client-rendered and `clean_html_to_text` returns little or nothing.
    """

    soup = BeautifulSoup(html, "html.parser")
    pieces: list[str] = []
    if soup.title and soup.title.string:
        pieces.append(soup.title.string.strip())
    for meta in soup.find_all("meta"):
        key = (meta.get("name") or meta.get("property") or "").lower()
        content = (meta.get("content") or "").strip()
        if not content or key not in (
            "description",
            "og:description",
            "og:title",
            "og:site_name",
            "twitter:description",
            "twitter:title",
        ):
            continue
        pieces.append(content)
    return " · ".join(dict.fromkeys(p for p in pieces if p))


def discover_internal_paths(
    html: str,
    host: str,
    *,
    limit: int = DEFAULT_DISCOVERY_LIMIT,
) -> list[str]:
    """Parse `<a>` hrefs from `html`, return internal paths whose last
    slug matches NAV_KEYWORDS. Deduped, leading slash. `host` is the
    bare domain of the page being parsed, used to keep same-host links
    when they appear as absolute URLs.
    """

    soup = BeautifulSoup(html, "html.parser")
    paths: list[str] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        path = _normalize_same_host(href, host)
        if not path:
            continue
        slug = path.rstrip("/").split("/")[-1].lower()
        if slug not in NAV_KEYWORDS:
            continue
        if path in seen:
            continue
        seen.add(path)
        paths.append(path)
        if len(paths) >= limit:
            break
    return paths


def _normalize_same_host(href: str, host: str) -> str | None:
    if href.startswith("//"):
        href = "https:" + href
    if href.startswith(("http://", "https://")):
        parsed = urlparse(href)
        if not parsed.netloc:
            return None
        this_host = parsed.netloc.lower()
        if this_host != host and this_host != f"www.{host}" and this_host != host.removeprefix("www."):
            return None
        path = parsed.path or "/"
    else:
        if not href.startswith("/"):
            href = "/" + href
        path = href.split("?", 1)[0].split("#", 1)[0]
    if not path.startswith("/"):
        return None
    # Skip obviously non-HTML targets
    if path.rsplit(".", 1)[-1].lower() in ("pdf", "png", "jpg", "jpeg", "gif", "svg", "webp", "zip"):
        return None
    return path
