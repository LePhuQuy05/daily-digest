"""Structured refs for the "Trong ngày" overview.

The writer keeps returning a plain `overview` string but marks each article
mention with ``[[n]]`` (0-based candidate index). This module turns those
markers into inline reference segments, guarantees coverage of every ranked
item, and provides a deterministic fallback overview.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Sequence

from daily_digest.config import Config
from daily_digest.model import SECTION_TITLES, SECTIONS, RankedItem

MAX_POINTS = 5
LABEL_MAX = 28
REST_TEXT = "Còn lại hôm nay: "
_MARKER_RE = re.compile(r"\[\[([^\]]{1,8})\]\]")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class OverviewRef:
    uid: str
    label: str
    title: str


@dataclass(frozen=True)
class OverviewSegment:
    text: str = ""
    ref: OverviewRef | None = None


@dataclass(frozen=True)
class OverviewPoint:
    segments: tuple[OverviewSegment, ...]
    kind: Literal["theme", "rest", "takeaway"] = "theme"


def short_label(title: str, number: int) -> str:
    """Compact reader-facing label; full title stays in the tooltip/aria."""
    base = title.split(":", 1)[0].strip() or title.strip()
    base = " ".join(base.split())
    if len(base) > LABEL_MAX:
        cut = base[:LABEL_MAX]
        last_space = cut.rfind(" ")
        if last_space > 0:
            cut = cut[:last_space]
        base = cut.rstrip(" ,;:.-") + "…"
    return base or f"Bài {number}"


def _normalize_text(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text)


def _strip_duplicate_label(text: str, label: str, title: str) -> str:
    """The writer sometimes repeats the title before its marker; drop it."""
    stripped = text.rstrip()
    for candidate in (label, title):
        if len(candidate) < 3 or not stripped.lower().endswith(candidate.lower()):
            continue
        prefix = stripped[: -len(candidate)]
        if prefix and prefix[-1].isalnum():
            continue  # don't cut inside a longer word
        prefix = prefix.rstrip()
        return prefix + " " if prefix else ""
    return text


def _split_points(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    if "\n" in text:
        raw = re.split(r"\n\s*\n|\n", text)
    else:
        raw = _SENTENCE_RE.split(text)
    points = [part.strip() for part in raw if part.strip()]
    if len(points) > MAX_POINTS:
        points = points[: MAX_POINTS - 1] + points[-1:]
    return points


def _parse_point(
    raw: str, ranked: Sequence[RankedItem], kind: Literal["theme", "takeaway"]
) -> OverviewPoint | None:
    segments: list[OverviewSegment] = []
    seen: set[int] = set()
    position = 0
    for match in _MARKER_RE.finditer(raw):
        before = raw[position : match.start()]
        try:
            index = int(match.group(1))
        except ValueError:
            index = -1
        valid = 0 <= index < len(ranked) and index not in seen
        if valid:
            item = ranked[index]
            label = short_label(item.item.title, index + 1)
            before = _strip_duplicate_label(before, label, item.item.title)
        if before:
            segments.append(OverviewSegment(text=_normalize_text(before)))
        if valid:
            item = ranked[index]
            segments.append(
                OverviewSegment(
                    ref=OverviewRef(
                        uid=item.item.id,
                        label=short_label(item.item.title, index + 1),
                        title=item.item.title,
                    )
                )
            )
            seen.add(index)
        position = match.end()
    tail = raw[position:]
    if tail:
        segments.append(OverviewSegment(text=_normalize_text(tail)))
    segments = [
        segment
        for segment in segments
        if segment.ref is not None or segment.text.strip()
    ]
    if not segments:
        return None
    return OverviewPoint(segments=tuple(segments), kind=kind)


def parse_overview(
    text: str, ranked: Sequence[RankedItem]
) -> tuple[OverviewPoint, ...]:
    """Split the prose into points and turn valid [[n]] markers into refs."""
    raw_points = _split_points(text)
    points: list[OverviewPoint] = []
    for index, raw in enumerate(raw_points):
        kind: Literal["theme", "takeaway"] = (
            "takeaway" if index == len(raw_points) - 1 else "theme"
        )
        point = _parse_point(raw, ranked, kind)
        if point is not None:
            points.append(point)
    return tuple(points)


def _ref_for(ranked: Sequence[RankedItem], index: int) -> OverviewRef:
    item = ranked[index]
    return OverviewRef(
        uid=item.item.id,
        label=short_label(item.item.title, index + 1),
        title=item.item.title,
    )


def ensure_coverage(
    points: Sequence[OverviewPoint], ranked: Sequence[RankedItem]
) -> tuple[OverviewPoint, ...]:
    """Guarantee every ranked item appears in at least one reference."""
    if not ranked:
        return tuple(points)
    covered = {
        segment.ref.uid
        for point in points
        for segment in point.segments
        if segment.ref is not None
    }
    missing = [
        (index, item)
        for index, item in enumerate(ranked)
        if item.item.id not in covered
    ]
    if not missing:
        return tuple(points)

    segments: list[OverviewSegment] = [OverviewSegment(text=REST_TEXT)]
    for offset, (index, _item) in enumerate(missing):
        if offset:
            segments.append(OverviewSegment(text=" · "))
        segments.append(OverviewSegment(ref=_ref_for(ranked, index)))

    rest = OverviewPoint(segments=tuple(segments), kind="rest")
    points = list(points)
    if points and points[-1].kind == "takeaway":
        points.insert(len(points) - 1, rest)
    else:
        points.append(rest)
    return tuple(points)


def heuristic_overview_points(
    ranked: Sequence[RankedItem], config: Config
) -> tuple[OverviewPoint, ...]:
    """Deterministic fallback: one section point, every item referenced."""
    points: list[OverviewPoint] = []
    for section in SECTIONS:
        items = [item for item in ranked if item.section == section]
        if not items:
            continue
        segments: list[OverviewSegment] = [
            OverviewSegment(text=f"{SECTION_TITLES[section]}: ")
        ]
        for offset, item in enumerate(items):
            if offset:
                segments.append(OverviewSegment(text=" · "))
            index = list(ranked).index(item)
            segments.append(
                OverviewSegment(
                    ref=OverviewRef(
                        uid=item.item.id,
                        label=short_label(item.item.title, index + 1),
                        title=item.item.title,
                    )
                )
            )
        points.append(OverviewPoint(segments=tuple(segments), kind="theme"))
    return tuple(points)
