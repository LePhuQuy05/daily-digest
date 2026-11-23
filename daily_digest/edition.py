"""Render-complete edition snapshots.

The HTML is the artifact. This sidecar records the exact render inputs that the
current ``digest_data`` blob cannot reconstruct (ordering, published dates,
overview points, pinned overflow, run metadata, artifact path/hash).
Images are deliberately not serialized: the current HTML is the media source.
"""

from __future__ import annotations

import dataclasses
import hashlib
import html as html_lib
import json
import re
import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from daily_digest.config import Config
from daily_digest.i18n import normalize_locale
from daily_digest.media import ImageAsset
from daily_digest.model import Item, Notice, RankedItem, Section
from daily_digest.overview import (
    OverviewPoint,
    OverviewRef,
    OverviewSegment,
    SectionBrief,
)
from daily_digest.render import build_digest_data, render_digest
from daily_digest.source_labels import labels_for
from daily_digest.util import LOG, atomic_write_text

SNAPSHOT_VERSION = 1
SNAPSHOT_DIR = "editions"
_DATE_LEN = 10


@dataclass(frozen=True)
class Edition:
    date: str
    locale: str
    ranked: tuple[RankedItem, ...]
    mode: str
    model_name: str
    degraded: bool = False
    sources_failed: tuple[str, ...] = ()
    overview: str = ""
    overview_points: tuple[OverviewPoint, ...] = ()
    notice_key: str = ""
    notice_params: Mapping[str, object] = field(default_factory=dict)
    notice_text: str = ""
    requested_count: int = 0
    backfilled_count: int = 0
    section_briefs: tuple[SectionBrief, ...] = ()
    notices: tuple[Notice, ...] = ()
    pinned: tuple[dict, ...] = ()
    pinned_overflow: int = 0
    images: Mapping[str, ImageAsset] = field(default_factory=dict)
    html_relpath: str = ""
    html_sha256: str = ""
    edition_id: str = ""
    schema_version: int = SNAPSHOT_VERSION


class EditionError(ValueError):
    """Snapshot is invalid for this build."""


def _valid_date(date: str) -> bool:
    if len(date) != _DATE_LEN:
        return False
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except (TypeError, ValueError):
        return False
    return True


def snapshot_path(output_dir: Path, date: str) -> Path:
    if not _valid_date(date):
        raise EditionError(f"invalid edition date: {date!r}")
    return output_dir / SNAPSHOT_DIR / f"digest-{date}.json"


def localize_status_path(output_dir: Path, date: str) -> Path:
    if not _valid_date(date):
        raise EditionError(f"invalid edition date: {date!r}")
    return output_dir / SNAPSHOT_DIR / f"localize-status-{date}.json"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def with_artifact(edition: Edition, path: Path, html: str, output_dir: Path) -> Edition:
    relpath = path.relative_to(output_dir).as_posix()
    return dataclasses.replace(
        edition,
        html_relpath=relpath,
        html_sha256=_sha256(html),
        edition_id=secrets.token_hex(8),
    )


def render_edition(edition: Edition, config: Config) -> str:
    return render_digest(
        list(edition.ranked),
        date=edition.date,
        mode=edition.mode,
        overview=edition.overview,
        overview_points=edition.overview_points,
        degraded=edition.degraded,
        sources_failed=list(edition.sources_failed),
        model_name=edition.model_name,
        template=config.template_path,
        notice=edition.notice_text,
        requested_count=edition.requested_count,
        backfilled_count=edition.backfilled_count,
        section_briefs=edition.section_briefs,
        notices=edition.notices,
        digest_data=build_digest_data(
            list(edition.ranked), list(edition.pinned), edition.date
        ),
        pinned=list(edition.pinned),
        pinned_overflow=edition.pinned_overflow,
        images=edition.images,
        source_names=labels_for(config),
        locale=edition.locale,
    )


def _item_to_dict(item: Item) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "url": item.url,
        "source": item.source,
        "points": item.points,
        "published": item.published.isoformat() if item.published else None,
        "summary": item.summary,
        "citations": item.citations,
        "section_hint": item.section_hint,
    }


def _ranked_to_dict(ranked_item: RankedItem) -> dict:
    return {
        "item": _item_to_dict(ranked_item.item),
        "why": ranked_item.why,
        "section": ranked_item.section,
        "llm_summary": ranked_item.llm_summary,
        "backfilled": ranked_item.backfilled,
    }


def _overview_to_dict(point: OverviewPoint) -> dict:
    return {
        "kind": point.kind,
        "segments": [
            {
                "text": segment.text,
                "ref": (
                    {
                        "uid": segment.ref.uid,
                        "label": segment.ref.label,
                        "title": segment.ref.title,
                    }
                    if segment.ref is not None
                    else None
                ),
            }
            for segment in point.segments
        ],
    }


def _int_or_zero(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _ref_to_dict(ref: OverviewRef) -> dict:
    return {"uid": ref.uid, "label": ref.label, "title": ref.title}


def _ref_from_dict(data: object) -> OverviewRef | None:
    if not isinstance(data, dict) or "uid" not in data:
        return None
    return OverviewRef(
        uid=str(data["uid"]),
        label=str(data.get("label", "")),
        title=str(data.get("title", "")),
    )


def _section_brief_to_dict(brief: SectionBrief) -> dict:
    return {
        "section": brief.section,
        "text": brief.text,
        "refs": [_ref_to_dict(ref) for ref in brief.refs],
        "coverage_refs": [_ref_to_dict(ref) for ref in brief.coverage_refs],
    }


def _section_brief_from_dict(data: object) -> SectionBrief | None:
    if not isinstance(data, dict):
        return None
    section = data.get("section")
    if section not in ("papers", "tech_news", "tools_releases"):
        return None
    refs = [
        ref
        for entry in data.get("refs", [])
        if (ref := _ref_from_dict(entry)) is not None
    ]
    coverage = [
        ref
        for entry in data.get("coverage_refs", [])
        if (ref := _ref_from_dict(entry)) is not None
    ]
    return SectionBrief(
        section=section,
        text=str(data.get("text", "")),
        refs=tuple(refs),
        coverage_refs=tuple(coverage),
    )


def _notice_to_dict(notice: Notice) -> dict:
    return {
        "key": notice.key,
        "params": dict(notice.params),
        "text": notice.text,
    }


def _notice_from_dict(data: object) -> Notice | None:
    if not isinstance(data, dict) or not data.get("key"):
        return None
    return Notice(
        key=str(data["key"]),
        params=dict(data.get("params") or {}),
        text=str(data.get("text", "")),
    )


def edition_to_dict(edition: Edition) -> dict:
    return {
        "version": edition.schema_version,
        "date": edition.date,
        "locale": normalize_locale(edition.locale) or "vi",
        "edition_id": edition.edition_id,
        "html_relpath": edition.html_relpath,
        "html_sha256": edition.html_sha256,
        "mode": edition.mode,
        "model_name": edition.model_name,
        "degraded": edition.degraded,
        "sources_failed": list(edition.sources_failed),
        "ranked": [_ranked_to_dict(ranked) for ranked in edition.ranked],
        "overview": edition.overview,
        "overview_points": [
            _overview_to_dict(point) for point in edition.overview_points
        ],
        "notice_key": edition.notice_key,
        "notice_params": dict(edition.notice_params),
        "notice_text": edition.notice_text,
        "requested_count": edition.requested_count,
        "backfilled_count": edition.backfilled_count,
        "section_briefs": [
            _section_brief_to_dict(brief) for brief in edition.section_briefs
        ],
        "notices": [_notice_to_dict(notice) for notice in edition.notices],
        "pinned": [dict(entry) for entry in edition.pinned],
        "pinned_overflow": edition.pinned_overflow,
    }


def save_edition(edition: Edition, output_dir: Path) -> Path:
    path = snapshot_path(output_dir, edition.date)
    atomic_write_text(
        path, json.dumps(edition_to_dict(edition), indent=2, ensure_ascii=False)
    )
    return path


def _item_from_dict(data: dict) -> Item:
    published = data.get("published")
    if published:
        published = datetime.fromisoformat(str(published))
    hint = data.get("section_hint")
    if hint not in ("papers", "tech_news", "tools_releases"):
        hint = None
    return Item(
        id=str(data["id"]),
        title=str(data.get("title", "")),
        url=str(data.get("url", "")),
        source=str(data.get("source", "")),
        points=data.get("points"),
        published=published,
        summary=str(data.get("summary", "")),
        citations=data.get("citations"),
        section_hint=hint,
    )


def _ranked_from_dict(data: dict) -> RankedItem:
    section = data.get("section")
    if section not in ("papers", "tech_news", "tools_releases"):
        section = "papers"
    return RankedItem(
        item=_item_from_dict(data["item"]),
        why=str(data.get("why", "")),
        section=section,
        llm_summary=str(data.get("llm_summary", "")),
        backfilled=bool(data.get("backfilled", False)),
    )


def _overview_from_dict(data: dict) -> OverviewPoint:
    segments: list[OverviewSegment] = []
    for segment in data.get("segments", []):
        ref_data = segment.get("ref")
        ref = (
            OverviewRef(
                uid=str(ref_data["uid"]),
                label=str(ref_data.get("label", "")),
                title=str(ref_data.get("title", "")),
            )
            if isinstance(ref_data, dict)
            else None
        )
        segments.append(OverviewSegment(text=str(segment.get("text", "")), ref=ref))
    kind = data.get("kind", "theme")
    if kind not in ("theme", "rest", "takeaway"):
        kind = "theme"
    return OverviewPoint(segments=tuple(segments), kind=kind)


def load_edition(output_dir: Path, date: str) -> Edition | None:
    """Load a valid snapshot; corrupt/old snapshots are treated as missing."""
    try:
        path = snapshot_path(output_dir, date)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return None
        if payload.get("version") != SNAPSHOT_VERSION:
            LOG.warning(
                "edition snapshot %s has unsupported version %r; ignoring",
                path,
                payload.get("version"),
            )
            return None
        if payload.get("date") != date:
            LOG.warning("edition snapshot %s has mismatched date; ignoring", path)
            return None
        ranked = tuple(_ranked_from_dict(entry) for entry in payload.get("ranked", []))
        points = tuple(
            _overview_from_dict(entry) for entry in payload.get("overview_points", [])
        )
        return Edition(
            date=date,
            locale=normalize_locale(payload.get("locale")) or "vi",
            ranked=ranked,
            mode=str(payload.get("mode", "llm")),
            model_name=str(payload.get("model_name", "")),
            degraded=bool(payload.get("degraded", False)),
            sources_failed=tuple(
                str(item) for item in payload.get("sources_failed", [])
            ),
            overview=str(payload.get("overview", "")),
            overview_points=points,
            notice_key=str(payload.get("notice_key", "")),
            notice_params=dict(payload.get("notice_params", {})),
            notice_text=str(payload.get("notice_text", "")),
            requested_count=_int_or_zero(payload.get("requested_count")),
            backfilled_count=_int_or_zero(payload.get("backfilled_count")),
            section_briefs=tuple(
                brief
                for entry in payload.get("section_briefs", [])
                if (brief := _section_brief_from_dict(entry)) is not None
            ),
            notices=tuple(
                notice
                for entry in payload.get("notices", [])
                if (notice := _notice_from_dict(entry)) is not None
            ),
            pinned=tuple(
                dict(entry)
                for entry in payload.get("pinned", [])
                if isinstance(entry, dict)
            ),
            pinned_overflow=int(payload.get("pinned_overflow", 0)),
            html_relpath=str(payload.get("html_relpath", "")),
            html_sha256=str(payload.get("html_sha256", "")),
            edition_id=str(payload.get("edition_id", "")),
            schema_version=SNAPSHOT_VERSION,
        )
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        LOG.warning("edition snapshot %s unreadable (%s); ignoring", date, exc)
        return None


_ARTICLE_RE = re.compile(r"<article\b([^>]*)>(.*?)</article>", re.S | re.I)
_DATE_JA_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")
_DATE_DOTS_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})")


def _attr(attrs: str, name: str) -> str:
    match = re.search(rf'\b{name}="([^"]*)"', attrs, re.I | re.S)
    return html_lib.unescape(match.group(1)) if match else ""


def _parse_display_date(text: str) -> datetime | None:
    cleaned = html_lib.unescape(text or "").strip()
    match = _DATE_JA_RE.search(cleaned)
    if match:
        year, month, day = (int(value) for value in match.groups())
        try:
            return datetime(year, month, day, tzinfo=timezone.utc)
        except ValueError:
            return None
    match = _DATE_DOTS_RE.search(cleaned)
    if match:
        day, month, year = (int(value) for value in match.groups())
        try:
            return datetime(year, month, day, tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _article_dates(html_text: str) -> dict[str, datetime]:
    dates: dict[str, datetime] = {}
    for match in _ARTICLE_RE.finditer(html_text):
        uid = _attr(match.group(1), "data-uid")
        if not uid:
            continue
        date_match = re.search(
            r'<span[^>]*class="paper-date"[^>]*>(.*?)</span>',
            match.group(2),
            re.S | re.I,
        )
        if date_match:
            parsed = _parse_display_date(date_match.group(1))
            if parsed is not None:
                dates[uid] = parsed
    return dates


def extract_images_from_html(html_text: str) -> dict[str, ImageAsset]:
    """Read the current page's embedded images by story uid.

    This is deliberately HTML-based: the current artifact is the media source,
    so cache eviction and backup moves cannot drop the cover.
    """
    images: dict[str, ImageAsset] = {}
    for match in _ARTICLE_RE.finditer(html_text):
        attrs, body = match.group(1), match.group(2)
        uid = _attr(attrs, "data-uid")
        if not uid:
            continue
        img_match = re.search(r"<img\b([^>]*)>", body, re.S | re.I)
        if not img_match:
            continue
        img_attrs = img_match.group(1)
        src = _attr(img_attrs, "src")
        if not src.startswith("data:"):
            continue
        credit_match = re.search(
            r"<figcaption[^>]*>(.*?)</figcaption>", body, re.S | re.I
        ) or re.search(r'<p[^>]*class="story-credit"[^>]*>(.*?)</p>', body, re.S | re.I)
        credit = ""
        if credit_match:
            credit = re.sub(r"<[^>]+>", " ", credit_match.group(1))
            credit = " ".join(html_lib.unescape(credit).split())
        try:
            width = int(_attr(img_attrs, "width") or 0)
            height = int(_attr(img_attrs, "height") or 0)
        except ValueError:
            width = height = 0
        images[uid] = ImageAsset(
            uid=uid,
            data_uri=src,
            alt=_attr(img_attrs, "alt"),
            credit=credit,
            source_url="",
            kind="og" if "story--cover" in attrs else "arxiv_img",
            width=width,
            height=height,
        )
    return images


def _legacy_model_name(html_text: str, config: Config) -> str:
    match = re.search(r"(?:Biên tập:|Edited by:|編集:)\s*([^<]+)", html_text, re.I)
    return match.group(1).strip() if match else config.llm.model


def edition_from_legacy_html(
    html_text: str,
    path: Path,
    config: Config,
    output_dir: Path | None = None,
) -> Edition | None:
    """Best-effort Edition for a digest created before sidecars existed.

    The item set/order comes from the embedded digest_data; paper dates and
    images come from the rendered HTML. Generated overview/notice text is
    intentionally discarded because it is in the old locale.
    """
    from daily_digest.popup_bridge import extract_digest_data

    data = extract_digest_data(html_text)
    if not isinstance(data, dict):
        return None
    raw_items = data.get("items")
    if not isinstance(raw_items, dict):
        return None
    date = str(data.get("date", ""))
    if not _valid_date(date):
        return None

    locale_match = re.search(r'<html[^>]*\blang="([^"]+)"', html_text, re.I)
    locale = normalize_locale(locale_match.group(1)) if locale_match else "vi"
    if locale is None:
        return None

    dates = _article_dates(html_text)
    ranked: list[RankedItem] = []
    for uid, snapshot in raw_items.items():
        if not isinstance(snapshot, dict):
            continue
        section = snapshot.get("section")
        if section not in ("papers", "tech_news", "tools_releases"):
            section = "papers"
        ranked.append(
            RankedItem(
                item=Item(
                    id=str(uid),
                    title=str(snapshot.get("title", "")),
                    url=str(snapshot.get("url", "")),
                    source=str(snapshot.get("source", "")),
                    points=snapshot.get("points"),
                    published=dates.get(str(uid)),
                    summary=str(snapshot.get("summary", "")),
                    citations=snapshot.get("citations"),
                    section_hint=None,
                ),
                why=str(snapshot.get("why", "")),
                section=section,
                llm_summary=str(snapshot.get("llm_summary", "")),
            )
        )

    pinned = tuple(
        dict(entry) for entry in data.get("pinned", []) if isinstance(entry, dict)
    )
    try:
        relpath = (
            path.relative_to(output_dir).as_posix()
            if output_dir is not None
            else path.name
        )
    except ValueError:
        relpath = path.name
    digest_sha = _sha256(html_text)
    mode = "empty" if not ranked and "empty-note" in html_text else "llm"
    return Edition(
        date=date,
        locale=locale,
        ranked=tuple(ranked),
        mode=mode,
        model_name=_legacy_model_name(html_text, config),
        degraded="status-strip degraded" in html_text,
        sources_failed=(),
        overview="",
        overview_points=(),
        notice_text="",
        pinned=pinned,
        pinned_overflow=0,
        images=extract_images_from_html(html_text),
        html_relpath=relpath,
        html_sha256=digest_sha,
        edition_id=f"legacy-{digest_sha[:16]}",
    )
