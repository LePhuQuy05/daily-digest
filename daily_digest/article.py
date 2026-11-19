"""Article-page text extraction: meta description / first-paragraph hydration.

Shared by the curated-feed source (feed entries with thin descriptions) and the
HN source (link posts carry no Algolia story text). All fetches go through
net.get_public so untrusted article URLs are SSRF-safe on every redirect hop.
"""

from __future__ import annotations

import html
import re
from dataclasses import replace

import httpx

from daily_digest.model import Item
from daily_digest.net import get_public

MAX_ARTICLE_BYTES = 2_000_000
MIN_DESCRIPTION_CHARS = 80
MAX_SUMMARY_CHARS = 1500
ARTICLE_TIMEOUT = 8.0
ARTICLE_USER_AGENT = "Mozilla/5.0 (compatible; DailyDigest/1.0)"
ARTICLE_ACCEPT = "text/html,*/*;q=0.8"

_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(r"<(script|style)\b.*?</\1>", re.IGNORECASE | re.DOTALL)
_META_RE = re.compile(r"<meta\b[^>]*>", re.IGNORECASE)
_ATTR_RE = re.compile(r"""([\w:-]+)\s*=\s*["']([^"']*)["']""")
_MAIN_RE = re.compile(r"<main\b.*?</main>", re.IGNORECASE | re.DOTALL)
_ARTICLE_RE = re.compile(r"<article\b.*?</article>", re.IGNORECASE | re.DOTALL)
_PARAGRAPH_RE = re.compile(r"<p\b[^>]*>(.*?)</p>", re.IGNORECASE | re.DOTALL)
_NAV_HINTS = ("Search models, datasets, users", "Ctrl K", "Skip to content")


def clean_html(value: str) -> str:
    text = _SCRIPT_RE.sub(" ", value or "")
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = " ".join(text.split())
    return re.sub(r"\s+([,.;:!?])", r"\1", text)


def meta_description(page: str) -> str:
    """Longest useful og/twitter/plain meta description on an article page."""
    best = ""
    for tag in _META_RE.findall(page):
        attrs = {key.lower(): value for key, value in _ATTR_RE.findall(tag)}
        key = (attrs.get("property") or attrs.get("name") or "").lower()
        if key not in ("og:description", "twitter:description", "description"):
            continue
        value = clean_html(attrs.get("content", ""))
        if len(value) > len(best):
            best = value
    return best[:MAX_SUMMARY_CHARS]


def article_lead(page: str) -> str:
    """First substantive paragraph of the article (fallback when meta is empty)."""
    scope = page
    for pattern in (_MAIN_RE, _ARTICLE_RE):
        match = pattern.search(page)
        if match:
            scope = match.group(0)
            break
    paragraphs = [clean_html(raw) for raw in _PARAGRAPH_RE.findall(scope)]
    paragraphs = [
        text
        for text in paragraphs
        if len(text) >= 120 and not any(hint in text for hint in _NAV_HINTS)
    ]
    for text in paragraphs:
        if len(text) >= 200:
            return text[:MAX_SUMMARY_CHARS]
    return paragraphs[0][:MAX_SUMMARY_CHARS] if paragraphs else ""


def hydrate_item(
    client: httpx.Client,
    item: Item,
    *,
    timeout: float = ARTICLE_TIMEOUT,
    max_bytes: int = MAX_ARTICLE_BYTES,
    min_chars: int = MIN_DESCRIPTION_CHARS,
) -> Item:
    """Fill a thin item summary from the article's meta description.

    Order: og/twitter/plain meta description -> first substantive paragraph.
    Best-effort: a blocked/slow/oversized page returns the item unchanged.
    """
    if len(item.summary) >= min_chars:
        return item
    try:
        response = get_public(
            client,
            item.url,
            headers={"User-Agent": ARTICLE_USER_AGENT, "Accept": ARTICLE_ACCEPT},
            timeout=timeout,
        )
        if len(response.content) > max_bytes:
            return item
        description = meta_description(response.text)
        if len(description) < min_chars:
            description = article_lead(response.text)
    except (httpx.HTTPError, OSError, TypeError, ValueError):
        return item
    if len(description) < min_chars:
        return item
    return replace(item, summary=description[:MAX_SUMMARY_CHARS])
