"""Render-complete edition snapshots.

The HTML is the artifact. This sidecar records the exact render inputs that the
current ``digest_data`` blob cannot reconstruct (ordering, published dates,
overview points, pinned overflow, run metadata, artifact path/hash).
Images are deliberately not serialized: the current HTML is the media source.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from daily_digest.config import Config
from daily_digest.i18n import normalize_locale
from daily_digest.media import ImageAsset
from daily_digest.model import Item, RankedItem, Section
from daily_digest.overview import (
    OverviewPoint,
    OverviewRef,
    OverviewSegment,
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
