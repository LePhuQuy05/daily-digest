"""Emergent Mind trending feed (https://www.emergentmind.com/feeds/rss — keyless).

Ranks arXiv papers by aggregated cross-platform attention (X, HN, Reddit, YouTube) —
a selection signal none of our other sources provide. Verified live 2026-11-19;
see docs/paper-sources.md for the survey and integration gotchas.

Feed quirks handled here:
- The feed covers ALL arXiv subjects (physics, math, astro...) — a topic filter
  keeps only AI/ML-relevant items (configurable, can be disabled).
- The item <link> is an Emergent Mind search URL, NOT the paper URL — the real
  arXiv id lives inside the CDATA description, so we extract it from there.
- <pubDate> is when Emergent Mind surfaced the paper, not the submission date —
  harmless because arXiv-id dedup handles cross-source overlap downstream.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

import httpx

from daily_digest.config import EmergentMindCfg
from daily_digest.model import Item
from daily_digest.normalize import find_arxiv_id

EMERGENT_MIND_RSS_URL = "https://www.emergentmind.com/feeds/rss"

_TAGS = re.compile(r"<[^>]+>")
_ARXIV_MARKER = re.compile(r"arxiv:", re.IGNORECASE)


def _clean_description(description: str) -> str:
    """Strip HTML, isolate the abstract between 'Abstract:' and the arXiv marker."""
    text = _TAGS.sub(" ", description)
    text = " ".join(text.split()).replace('"', '"').strip('" ').strip()
    start = text.lower().find("abstract:")
    if start >= 0:
        text = text[start + len("abstract:") :]
    marker = _ARXIV_MARKER.search(text)
    if marker:
        text = text[: marker.start()]
    return text.strip().strip('"').strip()


def _matches_topics(title: str, summary: str, topics: list[str]) -> bool:
    haystack = f"{title} {summary}".lower()
    return any(topic.lower() in haystack for topic in topics)


def parse_emergent_mind_rss(xml_text: str, cfg: EmergentMindCfg) -> list[Item]:
    root = ET.fromstring(xml_text)
    items: list[Item] = []
    seen_ids: set[str] = set()
    for entry in root.iter("item"):
        if len(items) >= cfg.max_items:
            break
        title = (entry.findtext("title") or "").strip()
        description = entry.findtext("description") or ""
        if not title:
            continue

        arxiv_id = find_arxiv_id(description)
        if not arxiv_id:
            continue  # not an arXiv paper (or malformed entry)

        summary = _clean_description(description)
        if cfg.require_topic and not _matches_topics(title, summary, cfg.topics):
            continue  # physics/math/astro noise from the all-subject feed

        if arxiv_id in seen_ids:
            continue
        seen_ids.add(arxiv_id)

        published: datetime | None = None
        try:
            raw_date = entry.findtext("pubDate")
            if raw_date:
                published = parsedate_to_datetime(raw_date)
        except (TypeError, ValueError):
            published = None

        items.append(
            Item(
                id=f"arxiv:{arxiv_id}",
                title=title,
                url=f"https://arxiv.org/abs/{arxiv_id}",
                source="emergentmind",
                points=None,  # the RSS feed carries no numbers; the signal is *being* in the feed
                published=published,
                summary=summary[:1500],
            )
        )
    return items


def fetch_emergent_mind(client: httpx.Client, cfg: EmergentMindCfg) -> list[Item]:
    response = client.get(EMERGENT_MIND_RSS_URL)
    response.raise_for_status()
    return parse_emergent_mind_rss(response.text, cfg)
