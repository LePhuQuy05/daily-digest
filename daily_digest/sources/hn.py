"""Hacker News front page via the Algolia API (keyless)."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import httpx

from daily_digest.config import HnCfg
from daily_digest.model import Item

ALGOLIA_URL = "https://hn.algolia.com/api/v1/search"
_TAGS = re.compile(r"<[^>]+>")


def fetch_hn(client: httpx.Client, cfg: HnCfg) -> list[Item]:
    response = client.get(
        ALGOLIA_URL, params={"tags": "front_page", "hitsPerPage": cfg.hits}
    )
    response.raise_for_status()
    hits = response.json().get("hits", [])

    items: list[Item] = []
    for hit in hits:
        object_id = str(hit.get("objectID") or "").strip()
        title = str(hit.get("title") or "").strip()
        points = int(hit.get("points") or 0)
        if not object_id or not title or points < cfg.min_points:
            continue
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}"
        created = hit.get("created_at_i")
        published = (
            datetime.fromtimestamp(created, tz=timezone.utc) if created else None
        )
        story_text = _TAGS.sub(" ", str(hit.get("story_text") or "")).strip()
        items.append(
            Item(
                id=f"hn:{object_id}",
                title=title,
                url=url,
                source="hn",
                points=points,
                published=published,
                summary=story_text[:400],
            )
        )
    return items
