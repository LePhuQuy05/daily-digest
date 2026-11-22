"""arXiv via the per-category announcement RSS feeds — these list papers *announced today*
(unlike the Atom API's submittedDate, which mixes in unannounced submissions)."""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from typing import Callable

import httpx

from daily_digest.config import ArxivCfg
from daily_digest.model import Item
from daily_digest.normalize import canonical_arxiv_id
from daily_digest.relevance import matches_topics

ARXIV_RSS_URL = "https://export.arxiv.org/rss/{category}"
USER_AGENT = "daily-digest/0.1 (personal research digest tool)"

_ANNOUNCE_TYPE = re.compile(r"Announce Type:\s*([a-z\-]+)")
_TITLE_SUFFIX = re.compile(r"\s*\((?:replaces|cross-list)[^)]*\)\s*$", re.IGNORECASE)


def _abstract_from(description: str) -> str:
    marker = description.find("Abstract:")
    if marker >= 0:
        return description[marker + len("Abstract:") :].strip()
    # Fallback: drop the "arXiv:<id> Announce Type: ..." header line
    return re.sub(r"^arXiv:.*$", "", description, flags=re.MULTILINE).strip()


def parse_rss(xml_text: str, cap: int) -> list[Item]:
    """Parse one category RSS feed; keep only brand-new announcements."""
    root = ET.fromstring(xml_text)
    items: list[Item] = []
    for entry in root.iter("item"):
        title = (entry.findtext("title") or "").strip()
        link = (entry.findtext("link") or "").strip()
        description = (entry.findtext("description") or "").strip()

        match = _ANNOUNCE_TYPE.search(description)
        announce_type = match.group(1) if match else "new"
        if announce_type != "new":  # skip replaces / cross-list
            continue
        if _TITLE_SUFFIX.search(title):
            continue

        arxiv_id = canonical_arxiv_id(link)
        if not arxiv_id or not title:
            continue
        items.append(
            Item(
                id=f"arxiv:{arxiv_id}",
                title=_TITLE_SUFFIX.sub("", title).strip(),
                url=f"https://arxiv.org/abs/{arxiv_id}",
                source="arxiv",
                points=None,
                published=None,  # RSS = announced today; recency handled by heuristic source weight
                summary=_abstract_from(description)[:1500],
            )
        )
        if len(items) >= cap:
            break
    return items


def fetch_arxiv(client: httpx.Client, cfg: ArxivCfg) -> list[Item]:
    items: list[Item] = []
    headers = {"User-Agent": USER_AGENT}
    for index, category in enumerate(cfg.categories):
        if index:
            time.sleep(cfg.pause_seconds)  # arXiv rate limit: ~1 request / 3s
        response = client.get(ARXIV_RSS_URL.format(category=category), headers=headers)
        response.raise_for_status()
        parsed = parse_rss(response.text, cfg.max_per_category)
        if category in cfg.filter_categories:
            parsed = [
                item
                for item in parsed
                if matches_topics(item.title, item.summary, cfg.filter_topics)
            ]
        items.extend(parsed)
    return items
