"""Shared HTML → text cleaning used by the web scrapers.

The goal is to drop global page chrome (navigation, footer, sidebars,
forms, ads) before entity extraction so spaCy isn't seeing "Privacy
policy" and the publication's own name on every page. When an
`<article>` or `<main>` tag is present we prefer its subtree.
"""

from __future__ import annotations

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
