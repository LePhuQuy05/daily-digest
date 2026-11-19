"""Hugging Face Daily Papers (curated trending papers, keyless). Falls back to yesterday's page
if today's is not populated yet (HF rolls the page around 00:00 UTC)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from daily_digest.config import HfPapersCfg
from daily_digest.model import Item

HF_DAILY_PAPERS_URL = "https://huggingface.co/api/daily_papers"


def _parse_timestamp(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def fetch_hf_papers(client: httpx.Client, cfg: HfPapersCfg) -> list[Item]:
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    entries: list[dict] = []
    for params in ({}, {"date": yesterday}):
        response = client.get(HF_DAILY_PAPERS_URL, params=params or None)
        response.raise_for_status()
        entries = response.json() or []
        if entries:
            break

    items: list[Item] = []
    for entry in entries[: cfg.max_items]:
        paper = entry.get("paper") or {}
        paper_id = str(paper.get("id") or "").strip()
        title = str(paper.get("title") or "").strip()
        if not paper_id or not title:
            continue
        items.append(
            Item(
                id=f"arxiv:{paper_id}",
                title=title,
                url=f"https://arxiv.org/abs/{paper_id}",
                source="hf_papers",
                points=int(paper.get("upvotes") or 0),
                published=_parse_timestamp(paper.get("publishedAt")),
                summary=str(paper.get("summary") or "")[:1500],
            )
        )
    return items
