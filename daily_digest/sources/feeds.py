"""Curated RSS/Atom feeds for Tech News and Tools & Releases.

One source covers many feeds so adding a reputable publication is a config
change, not a new module. Each feed fails independently: a dead or rate-limited
feed only shrinks that day's candidate pool.
"""

from __future__ import annotations

import hashlib
import html
import re
import xml.etree.ElementTree as ET
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import httpx

from daily_digest.config import FeedEntry, FeedsCfg
from daily_digest.model import Item
from daily_digest.normalize import normalize_url
from daily_digest.relevance import matches_topics
from daily_digest.util import LOG

FEED_USER_AGENT = "Mozilla/5.0 (compatible; DailyDigest/1.0)"
FEED_ACCEPT = (
    "application/rss+xml, application/atom+xml, application/xml, "
    "text/xml;q=0.9, */*;q=0.8"
)
MAX_FEED_BYTES = 5_000_000
MAX_ARTICLE_BYTES = 2_000_000
MAX_SUMMARY_CHARS = 1500
MIN_HYDRATED_SUMMARY = 80
REQUEST_TIMEOUT = 15.0
HYDRATE_TIMEOUT = 8.0

_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(r"<(script|style)\b.*?</\1>", re.IGNORECASE | re.DOTALL)
_META_RE = re.compile(r"<meta\b[^>]*>", re.IGNORECASE)
_ATTR_RE = re.compile(r"""([\w:-]+)\s*=\s*["']([^"']*)["']""")
_MAIN_RE = re.compile(r"<main\b.*?</main>", re.IGNORECASE | re.DOTALL)
_ARTICLE_RE = re.compile(r"<article\b.*?</article>", re.IGNORECASE | re.DOTALL)
_PARAGRAPH_RE = re.compile(r"<p\b[^>]*>(.*?)</p>", re.IGNORECASE | re.DOTALL)
_NAV_HINTS = ("Search models, datasets, users", "Ctrl K", "Skip to content")
# Stable releases only: rc/build/dev tags are noisy for a daily digest.
_PRERELEASE_RE = re.compile(
    r"(rc\d+|\.dev\b|\bnightly\b|\bcanary\b|\bpreview\b|\balpha\b|\bbeta\b|trunk/)",
    re.IGNORECASE,
)
_UNSTABLE_URL_RE = re.compile(
    r"(rc\d+|\.dev\b|/trunk/|/nightly|/canary)", re.IGNORECASE
)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _clean_html(value: str) -> str:
    text = _SCRIPT_RE.sub(" ", value or "")
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = " ".join(text.split())
    return re.sub(r"\s+([,.;:!?])", r"\1", text)


def _child_text(node: ET.Element, *names: str) -> str:
    for child in node:
        if _local(child.tag) in names:
            text = " ".join(child.itertext()).strip()
            if text:
                return text
    return ""


def _link(node: ET.Element) -> str:
    for child in node:
        if _local(child.tag) != "link":
            continue
        href = (child.attrib.get("href") or "").strip()
        if href:
            return href
        text = (child.text or "").strip()
        if text:
            return text
    for name in ("guid", "id"):
        value = _child_text(node, name).strip()
        if value.lower().startswith(("http://", "https://")):
            return value
    return ""


def _published(node: ET.Element) -> datetime | None:
    for child in node:
        if _local(child.tag) not in ("pubDate", "published", "updated"):
            continue
        raw = (child.text or "").strip()
        if not raw:
            continue
        try:
            if "," in raw or raw[:3].isalpha():
                parsed = parsedate_to_datetime(raw)
            else:
                parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    return None


def _summary(node: ET.Element) -> str:
    candidates: list[str] = []
    for child in node:
        if _local(child.tag) in (
            "description",
            "summary",
            "content",
            "encoded",
            "subtitle",
        ):
            cleaned = _clean_html(" ".join(child.itertext()))
            if cleaned:
                candidates.append(cleaned)
    summary = max(candidates, key=len) if candidates else ""
    if len(summary) < MIN_HYDRATED_SUMMARY:
        categories = [
            _clean_html(" ".join(child.itertext()))
            for child in node
            if _local(child.tag) == "category"
        ]
        categories = [value for value in dict.fromkeys(categories) if value]
        if categories:
            parts = [summary, *categories]
            summary = " · ".join(dict.fromkeys(part for part in parts if part))
    return summary[:MAX_SUMMARY_CHARS]


def _meta_description(page: str) -> str:
    """Longest useful og/twitter/plain meta description on an article page."""
    best = ""
    for tag in _META_RE.findall(page):
        attrs = {key.lower(): value for key, value in _ATTR_RE.findall(tag)}
        key = (attrs.get("property") or attrs.get("name") or "").lower()
        if key not in ("og:description", "twitter:description", "description"):
            continue
        value = _clean_html(attrs.get("content", ""))
        if len(value) > len(best):
            best = value
    return best[:MAX_SUMMARY_CHARS]


def _article_lead(page: str) -> str:
    """First substantive paragraph of the article (fallback when meta is empty)."""
    scope = page
    for pattern in (_MAIN_RE, _ARTICLE_RE):
        match = pattern.search(page)
        if match:
            scope = match.group(0)
            break
    paragraphs = [_clean_html(raw) for raw in _PARAGRAPH_RE.findall(scope)]
    paragraphs = [
        text
        for text in paragraphs
        if len(text) >= 120 and not any(hint in text for hint in _NAV_HINTS)
    ]
    for text in paragraphs:
        if len(text) >= 200:
            return text[:MAX_SUMMARY_CHARS]
    return paragraphs[0][:MAX_SUMMARY_CHARS] if paragraphs else ""


def _hydrate(client: httpx.Client, item: Item) -> Item:
    """Fill a thin feed summary from the article's meta description.

    Best-effort: a blocked/slow page keeps the original (often empty) summary;
    the writer prompt already handles title-only items.
    """
    if len(item.summary) >= MIN_HYDRATED_SUMMARY:
        return item
    try:
        response = client.get(
            item.url,
            headers={"User-Agent": FEED_USER_AGENT, "Accept": "text/html,*/*;q=0.8"},
            timeout=HYDRATE_TIMEOUT,
        )
        response.raise_for_status()
        if len(response.content) > MAX_ARTICLE_BYTES:
            return item
        description = _meta_description(response.text)
        if len(description) < MIN_HYDRATED_SUMMARY:
            description = _article_lead(response.text)
    except (httpx.HTTPError, TypeError, ValueError):
        return item
    if len(description) < MIN_HYDRATED_SUMMARY:
        return item
    return replace(item, summary=description)


def _item_id(url: str) -> str:
    digest = hashlib.sha1(normalize_url(url).encode("utf-8")).hexdigest()[:12]
    return f"feed:{digest}"


def parse_feed(xml_text: str, entry: FeedEntry, topics: list[str]) -> list[Item]:
    """Parse RSS 2.0 or Atom, applying age, topic and prerelease filters."""
    root = ET.fromstring(xml_text)
    nodes = [node for node in root.iter() if _local(node.tag) in ("item", "entry")]
    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=entry.max_age_days)
        if entry.max_age_days
        else None
    )
    items: list[Item] = []
    seen_urls: set[str] = set()
    for node in nodes:
        title = _clean_html(_child_text(node, "title"))
        if not title:
            continue
        url = _link(node).strip()
        if not url.lower().startswith(("http://", "https://")):
            continue
        if entry.section == "tools_releases" and (
            _PRERELEASE_RE.search(title) or _UNSTABLE_URL_RE.search(url)
        ):
            continue
        published = _published(node)
        if cutoff is not None and published is not None and published < cutoff:
            continue
        summary = _summary(node)
        if entry.require_topic and not matches_topics(title, summary, topics):
            continue
        normalized = normalize_url(url)
        if normalized in seen_urls:
            continue
        seen_urls.add(normalized)
        items.append(
            Item(
                id=_item_id(url),
                title=title,
                url=url,
                source=entry.name,
                points=None,
                published=published,
                summary=summary,
                section_hint=entry.section,
            )
        )
        if len(items) >= entry.max_items:
            break
    return items


def fetch_feeds(client: httpx.Client, cfg: FeedsCfg) -> list[Item]:
    """Fetch every configured feed. A partial failure is logged, not fatal."""
    items: list[Item] = []
    failures = 0
    for entry in cfg.entries:
        try:
            response = client.get(
                entry.url,
                headers={"User-Agent": FEED_USER_AGENT, "Accept": FEED_ACCEPT},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            if len(response.content) > MAX_FEED_BYTES:
                raise ValueError(f"feed larger than {MAX_FEED_BYTES} bytes")
            parsed = parse_feed(response.text, entry, cfg.topics)
        except (httpx.HTTPError, ET.ParseError, TypeError, ValueError) as exc:
            failures += 1
            LOG.warning(
                "feed '%s' (%s) failed: %s: %s",
                entry.name,
                entry.label or entry.name,
                type(exc).__name__,
                exc,
            )
            continue
        if entry.hydrate:
            parsed = [_hydrate(client, item) for item in parsed]
        items.extend(parsed)
        LOG.info("feed %s: %d items", entry.name, len(parsed))
    if cfg.entries and failures == len(cfg.entries):
        raise ValueError("all configured feeds failed")
    return items
