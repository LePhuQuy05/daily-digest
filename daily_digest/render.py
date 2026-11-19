"""HTML digest rendering + atomic archiving."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from daily_digest.frontpage import build_front_page
from daily_digest.media import ImageAsset
from daily_digest.model import RankedItem
from daily_digest.normalize import safe_href
from daily_digest.util import atomic_write_text

SOURCE_NAMES = {
    "hn": "Hacker News",
    "arxiv": "arXiv",
    "hf_papers": "HF Papers",
    "emergentmind": "Emergent Mind",
    "alphaxiv": "alphaXiv",
}

_VI_WEEKDAYS = (
    "THỨ HAI",
    "THỨ BA",
    "THỨ TƯ",
    "THỨ NĂM",
    "THỨ SÁU",
    "THỨ BẢY",
    "CHỦ NHẬT",
)


def _format_date_long(date: str) -> str:
    """'2026-11-19' -> 'THỨ NĂM, 19.11.2026'; invalid input falls back verbatim."""
    try:
        parsed = datetime.strptime(date, "%Y-%m-%d")
    except (TypeError, ValueError):
        return date
    return f"{_VI_WEEKDAYS[parsed.weekday()]}, {parsed:%d.%m.%Y}"


def build_digest_data(ranked: list[RankedItem], pinned: list[dict], date: str) -> dict:
    """The data blob embedded in every digest HTML (consumed by the popup bridge).

    Plain dicts only — datetime/None-safe, JSON-serializable by construction.
    Top-level `date` is mandatory: latest.html carries no date in its filename.
    `items` maps uid -> snapshot so feedback/ask actions know what they acted on."""
    return {
        "date": date,
        "items": {
            ranked_item.item.id: {
                "title": ranked_item.item.title,
                "url": ranked_item.item.url,
                "source": ranked_item.item.source,
                "points": ranked_item.item.points,
                "citations": ranked_item.item.citations,
                "summary": ranked_item.item.summary,
                "llm_summary": ranked_item.llm_summary,
                "why": ranked_item.why,
                "section": ranked_item.section,
            }
            for ranked_item in ranked
        },
        "pinned": [dict(entry) for entry in pinned],
    }


def render_digest(
    ranked: list[RankedItem],
    *,
    date: str,
    mode: str,
    degraded: bool,
    sources_failed: list[str],
    model_name: str,
    template: Path,
    overview: str = "",
    overview_label: str = "Today's overview",
    notice: str = "",
    digest_data: dict | None = None,
    pinned: list[dict] = (),
    pinned_overflow: int = 0,
    images: Mapping[str, ImageAsset] | None = None,
) -> str:
    env = Environment(loader=FileSystemLoader(template.parent), autoescape=True)
    env.filters["safe_href"] = safe_href
    tpl = env.get_template(template.name)
    front_page = build_front_page(ranked)
    return tpl.render(
        date=date,
        date_long=_format_date_long(date),
        mode=mode,
        model_name=model_name,
        degraded=degraded,
        sources_failed=sources_failed,
        overview=overview,
        overview_label=overview_label,
        notice=notice,
        digest_data=digest_data,
        pinned=list(pinned),
        pinned_overflow=pinned_overflow,
        front_page=front_page,
        images=images or {},
        source_names=SOURCE_NAMES,
        total=len(ranked),
    )


def write_digest(html: str, output_dir: Path, date: str) -> Path:
    """Archive digest-YYYY-MM-DD.html atomically; if the target is locked (open in a browser),
    fall back to digest-YYYY-MM-DD-2.html. Always refresh latest.html."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"digest-{date}.html"
    try:
        atomic_write_text(path, html)
    except PermissionError:
        path = output_dir / f"digest-{date}-2.html"
        atomic_write_text(path, html)
    atomic_write_text(output_dir / "latest.html", html)
    return path
