"""HTML digest rendering + atomic archiving."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from daily_digest.frontpage import build_front_page
from daily_digest.i18n import (
    LOCALE_LABEL,
    SUPPORTED_LOCALES,
    format_date_long,
    format_short_date,
    js_messages,
    locale_strings,
    normalize_locale,
    section_title,
    split_sentences,
    t,
)
from daily_digest.media import ImageAsset
from daily_digest.model import RankedItem
from daily_digest.normalize import safe_href
from daily_digest.overview import OverviewPoint
from daily_digest.source_labels import SOURCE_LABELS
from daily_digest.util import atomic_write_text, today_str

SOURCE_NAMES = SOURCE_LABELS

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
    """Backward-compatible vi date formatter."""
    return format_date_long(date, "vi")


def _short_date(value: datetime | None) -> str:
    """Backward-compatible vi paper date formatter."""
    return format_short_date(value, "vi")


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
    overview_label: str | None = None,
    overview_points: Sequence[OverviewPoint] = (),
    notice: str = "",
    digest_data: dict | None = None,
    pinned: list[dict] = (),
    pinned_overflow: int = 0,
    images: Mapping[str, ImageAsset] | None = None,
    source_names: Mapping[str, str] | None = None,
    locale: str = "vi",
) -> str:
    locale = normalize_locale(locale) or "vi"
    env = Environment(loader=FileSystemLoader(template.parent), autoescape=True)
    env.filters["safe_href"] = safe_href
    env.filters["short_date"] = lambda value: format_short_date(value, locale)
    env.filters["split_overview"] = lambda value: split_sentences(value, locale)
    tpl = env.get_template(template.name)
    front_page = build_front_page(ranked)
    strings = locale_strings(locale)
    resolved_overview_label = overview_label or t(locale, "overview_label")
    return tpl.render(
        date=date,
        date_long=format_date_long(date, locale),
        mode=mode,
        model_name=model_name,
        degraded=degraded,
        sources_failed=sources_failed,
        overview=overview,
        overview_label=resolved_overview_label,
        overview_points=overview_points,
        notice=notice,
        digest_data=digest_data,
        pinned=list(pinned),
        pinned_overflow=pinned_overflow,
        front_page=front_page,
        images=images or {},
        source_names={**SOURCE_NAMES, **(source_names or {})},
        total=len(ranked),
        locale=locale,
        t=strings,
        messages=js_messages(locale),
        languages=[(code, LOCALE_LABEL[code]) for code in SUPPORTED_LOCALES],
        section_titles={
            key: section_title(key, locale)
            for key in ("papers", "tech_news", "tools_releases")
        },
    )


def write_digest(
    html: str,
    output_dir: Path,
    date: str,
    *,
    update_latest: bool | None = None,
    preferred_path: Path | None = None,
) -> Path:
    """Archive digest HTML atomically; refresh latest.html only for today.

    ``preferred_path`` preserves the actual opened artifact (e.g. ``-2.html``).
    If it is locked, fall back to a canonical/alternate file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    if preferred_path is not None:
        path = preferred_path
        try:
            atomic_write_text(path, html)
        except PermissionError:
            path = output_dir / f"digest-{date}.html"
            if path == preferred_path:
                path = output_dir / f"digest-{date}-2.html"
            atomic_write_text(path, html)
    else:
        path = output_dir / f"digest-{date}.html"
        try:
            atomic_write_text(path, html)
        except PermissionError:
            path = output_dir / f"digest-{date}-2.html"
            atomic_write_text(path, html)
    if update_latest is None:
        update_latest = date == today_str()
    if update_latest:
        atomic_write_text(output_dir / "latest.html", html)
    return path
