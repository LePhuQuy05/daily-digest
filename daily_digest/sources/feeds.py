"""Curated RSS/Atom feeds for Tech News and Tools & Releases.

One source covers many feeds so adding a reputable publication is a config
change, not a new module. Each feed fails independently: a dead or rate-limited
feed only shrinks that day's candidate pool.
"""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import httpx

from daily_digest.article import (
    MAX_SUMMARY_CHARS,
    MIN_DESCRIPTION_CHARS,
    clean_html,
    hydrate_item,
)
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
REQUEST_TIMEOUT = 15.0

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
            cleaned = clean_html(" ".join(child.itertext()))
            if cleaned:
                candidates.append(cleaned)
    summary = max(candidates, key=len) if candidates else ""
    if len(summary) < MIN_DESCRIPTION_CHARS:
        categories = [
            clean_html(" ".join(child.itertext()))
            for child in node
            if _local(child.tag) == "category"
        ]
        categories = [value for value in dict.fromkeys(categories) if value]
        if categories:
            parts = [summary, *categories]
            summary = " · ".join(dict.fromkeys(part for part in parts if part))
    return summary[:MAX_SUMMARY_CHARS]


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
        title = clean_html(_child_text(node, "title"))
        if not title:
            continue
        lowered = title.lower()
        if any(needle.lower() in lowered for needle in entry.exclude):
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


def _fetch_entry(client: httpx.Client, entry: FeedEntry, cfg: FeedsCfg) -> list[Item]:
    """Fetch + parse one feed. Raises on HTTP/parse/size errors."""
    response = client.get(
        entry.url,
        headers={"User-Agent": FEED_USER_AGENT, "Accept": FEED_ACCEPT},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    if len(response.content) > MAX_FEED_BYTES:
        raise ValueError(f"feed larger than {MAX_FEED_BYTES} bytes")
    return parse_feed(response.text, entry, cfg.topics)


def fetch_feeds(client: httpx.Client, cfg: FeedsCfg) -> list[Item]:
    """Fetch every configured feed. A partial failure is logged, not fatal."""
    items: list[Item] = []
    failures = 0
    for entry in cfg.entries:
        try:
            parsed = _fetch_entry(client, entry, cfg)
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
            parsed = [hydrate_item(client, item) for item in parsed]
        items.extend(parsed)
        LOG.info("feed %s: %d items", entry.name, len(parsed))
    if cfg.entries and failures == len(cfg.entries):
        raise ValueError("all configured feeds failed")
    return items


@dataclass(frozen=True)
class FeedHealth:
    """Status of one configured feed (for `daily-digest health`)."""

    name: str
    url: str
    label: str
    ok: bool
    item_count: int = 0
    error: str = ""


def check_feeds(client: httpx.Client, cfg: FeedsCfg) -> list[FeedHealth]:
    """Per-feed status; never raises and never hydrates (fast drill-down)."""
    health: list[FeedHealth] = []
    for entry in cfg.entries:
        try:
            parsed = _fetch_entry(client, entry, cfg)
        except (httpx.HTTPError, ET.ParseError, TypeError, ValueError) as exc:
            health.append(
                FeedHealth(
                    name=entry.name,
                    url=entry.url,
                    label=entry.label or entry.name,
                    ok=False,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
            continue
        health.append(
            FeedHealth(
                name=entry.name,
                url=entry.url,
                label=entry.label or entry.name,
                ok=True,
                item_count=len(parsed),
            )
        )
    return health
