"""Structured refs for the day overview.

The writer keeps returning a plain ``overview`` string but marks each article
mention with ``[[n]]`` (0-based candidate index). This module turns those
markers into inline reference segments, guarantees coverage of every ranked
item, and provides a deterministic fallback overview.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Sequence

from daily_digest.config import Config
from daily_digest.i18n import (
    normalize_locale,
    normalize_markers,
    section_title,
    split_sentences,
    t,
    takeaway_marker,
)
from daily_digest.model import SECTIONS, RankedItem, Section

MAX_POINTS = 5
REST_CHUNK = 8
LABEL_MAX = 28
LABEL_MAX_JA = 13
REST_TEXT = "Còn lại hôm nay: "  # backwards-compatible vi constant
_MARKER_RE = re.compile(r"\[\[([^\]]{1,8})\]\]")


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


SECTION_BRIEF_MAX = 600
SECTION_BRIEF_MAX_JA = 360
SECTION_BRIEF_REFS = 3


@dataclass(frozen=True)
class SectionBrief:
    """A bounded per-section summary plus inline refs and anchor coverage."""

    section: Section
    text: str
    refs: tuple[OverviewRef, ...] = ()
    coverage_refs: tuple[OverviewRef, ...] = ()
    segments: tuple[OverviewSegment, ...] = ()


def short_label(title: str, number: int, locale: str = "vi") -> str:
    """Compact reader-facing label; full title stays in the tooltip/aria."""
    loc = normalize_locale(locale) or "vi"
    base = re.split(r"[:：]", title, maxsplit=1)[0].strip() or title.strip()
    base = " ".join(base.split())
    limit = LABEL_MAX_JA if loc == "ja" else LABEL_MAX
    if len(base) > limit:
        cut = base[:limit]
        if loc != "ja":
            last_space = cut.rfind(" ")
            if last_space > 0:
                cut = cut[:last_space]
        base = cut.rstrip(" ,;:.-。、！？") + "…"
    return base or t(loc, "overview_story_n").format(n=number)


def _normalize_text(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text)


def _strip_duplicate_label(
    text: str, label: str, title: str, locale: str = "vi"
) -> str:
    """The writer sometimes repeats the title before its marker; drop it."""
    stripped = text.rstrip()
    loc = normalize_locale(locale) or "vi"
    for candidate in (label, title):
        if len(candidate) < 3 or not stripped.lower().endswith(candidate.lower()):
            continue
        prefix = stripped[: -len(candidate)]
        if not prefix:
            return ""
        last = prefix[-1]
        if last in "「『（【\"'":
            continue  # never cut immediately after an opening quote/bracket
        if last.isascii() and last.isalnum():
            continue  # don't cut inside a longer Latin word
        prefix = prefix.rstrip()
        if not prefix:
            return ""
        if loc != "ja" and not prefix.endswith((" ", "\t")):
            prefix += " "
        return prefix
    return text


def split_overview_points(text: str, locale: str = "vi") -> list[str]:
    """Split into display points: blank-line paragraphs first, sentences second.

    A multi-paragraph overview is already structured; splitting every sentence
    again breaks the writer's intended point boundaries. A single paragraph
    still needs sentence splitting.
    """
    cleaned = normalize_markers(text)
    paragraphs = [
        part.strip() for part in re.split(r"\n\s*\n", cleaned) if part.strip()
    ]
    if len(paragraphs) >= 2:
        points = paragraphs
    else:
        points = split_sentences(cleaned, locale)
    if len(points) > MAX_POINTS:
        points = points[: MAX_POINTS - 1] + points[-1:]
    return points


def _split_points(text: str, locale: str) -> list[str]:
    return split_overview_points(text, locale)


def _is_takeaway(raw: str, locale: str) -> bool:
    marker = takeaway_marker(locale).strip().lower().replace("：", ":")
    head = raw.lstrip().lower().replace("：", ":")
    return bool(marker) and head.startswith(marker)


def _parse_point(
    raw: str,
    ranked: Sequence[RankedItem],
    kind: Literal["theme", "takeaway"],
    locale: str = "vi",
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
            label = short_label(item.item.title, index + 1, locale)
            before = _strip_duplicate_label(before, label, item.item.title, locale)
        if before:
            segments.append(OverviewSegment(text=_normalize_text(before)))
        if valid:
            item = ranked[index]
            segments.append(
                OverviewSegment(
                    ref=OverviewRef(
                        uid=item.item.id,
                        label=short_label(item.item.title, index + 1, locale),
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
    text: str, ranked: Sequence[RankedItem], locale: str = "vi"
) -> tuple[OverviewPoint, ...]:
    """Split the prose into points and turn valid [[n]] markers into refs."""
    raw_points = _split_points(text, locale)
    points: list[OverviewPoint] = []
    for raw in raw_points:
        kind: Literal["theme", "takeaway"] = (
            "takeaway" if _is_takeaway(raw, locale) else "theme"
        )
        point = _parse_point(raw, ranked, kind, locale)
        if point is not None:
            points.append(point)
    return tuple(points)


def _ref_for(
    ranked: Sequence[RankedItem], index: int, locale: str = "vi"
) -> OverviewRef:
    item = ranked[index]
    return OverviewRef(
        uid=item.item.id,
        label=short_label(item.item.title, index + 1, locale),
        title=item.item.title,
    )


def ensure_coverage(
    points: Sequence[OverviewPoint], ranked: Sequence[RankedItem], locale: str = "vi"
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

    rest_points: list[OverviewPoint] = []
    for start in range(0, len(missing), REST_CHUNK):
        chunk = missing[start : start + REST_CHUNK]
        segments: list[OverviewSegment] = [
            OverviewSegment(text=t(locale, "overview_rest"))
        ]
        for offset, (index, _item) in enumerate(chunk):
            if offset:
                segments.append(OverviewSegment(text=" · "))
            segments.append(OverviewSegment(ref=_ref_for(ranked, index, locale)))
        rest_points.append(OverviewPoint(segments=tuple(segments), kind="rest"))

    points = list(points)
    if points and points[-1].kind == "takeaway":
        points[len(points) - 1 : len(points) - 1] = rest_points
    else:
        points.extend(rest_points)
    return tuple(points)


def heuristic_overview_points(
    ranked: Sequence[RankedItem], config: Config, locale: str = "vi"
) -> tuple[OverviewPoint, ...]:
    """Deterministic fallback: one section point, every item referenced."""
    points: list[OverviewPoint] = []
    for section in SECTIONS:
        items = [item for item in ranked if item.section == section]
        if not items:
            continue
        segments: list[OverviewSegment] = [
            OverviewSegment(text=f"{section_title(section, locale)}: ")
        ]
        for offset, item in enumerate(items):
            if offset:
                segments.append(OverviewSegment(text=" · "))
            index = list(ranked).index(item)
            segments.append(
                OverviewSegment(
                    ref=OverviewRef(
                        uid=item.item.id,
                        label=short_label(item.item.title, index + 1, locale),
                        title=item.item.title,
                    )
                )
            )
        points.append(OverviewPoint(segments=tuple(segments), kind="theme"))
    return tuple(points)


def section_brief_cap(locale: str = "vi") -> int:
    return (
        SECTION_BRIEF_MAX_JA
        if (normalize_locale(locale) or "vi") == "ja"
        else SECTION_BRIEF_MAX
    )


def truncate_section_brief(text: str, locale: str = "vi") -> str:
    """Cap a section brief at a sentence or word boundary."""
    cap = section_brief_cap(locale)
    cleaned = " ".join(text.split())
    if len(cleaned) <= cap:
        return cleaned
    cut = cleaned[:cap]
    last_sentence = max((cut.rfind(ch) for ch in "\u3002\uff01\uff1f.!?"), default=-1)
    if last_sentence >= cap // 2:
        return cut[: last_sentence + 1].rstrip()
    last_space = cut.rfind(" ")
    if last_space >= cap // 2:
        return cut[:last_space].rstrip()
    return cut.rstrip()


def section_items(
    ranked: Sequence[RankedItem], section: Section
) -> list[tuple[int, RankedItem]]:
    return [
        (index, item) for index, item in enumerate(ranked) if item.section == section
    ]


def heuristic_section_briefs(
    ranked: Sequence[RankedItem], config: Config, locale: str = "vi"
) -> tuple[SectionBrief, ...]:
    """Deterministic fallback: one bounded brief per non-empty section."""
    loc = normalize_locale(locale) or "vi"
    briefs: list[SectionBrief] = []
    for section in SECTIONS:
        items = section_items(ranked, section)
        if not items:
            continue
        titles = " \u00b7 ".join(item.item.title for _, item in items[:3])
        text = t(loc, "section_brief_fallback").format(n=len(items), titles=titles)
        segments: list[OverviewSegment] = [
            OverviewSegment(
                text=t(loc, "section_brief_fallback_prefix").format(n=len(items))
            )
        ]
        for offset, (index, _item) in enumerate(items):
            if offset:
                segments.append(OverviewSegment(text=" \u00b7 "))
            segments.append(OverviewSegment(ref=_ref_for(ranked, index, loc)))
        refs = tuple(
            _ref_for(ranked, index, loc) for index, _ in items[:SECTION_BRIEF_REFS]
        )
        coverage = tuple(
            _ref_for(ranked, index, loc) for index, _ in items[SECTION_BRIEF_REFS:]
        )
        briefs.append(
            SectionBrief(
                section=section,
                text=truncate_section_brief(text, loc),
                refs=refs,
                coverage_refs=coverage,
                segments=tuple(segments),
            )
        )
    return tuple(briefs)


def complete_section_briefs(
    briefs: Sequence[SectionBrief],
    ranked: Sequence[RankedItem],
    config: Config,
    locale: str = "vi",
) -> tuple[SectionBrief, ...]:
    """Fill missing sections and guarantee every section item has an anchor."""
    loc = normalize_locale(locale) or "vi"
    by_section = {
        brief.section: brief
        for brief in briefs
        if brief.section in SECTIONS and brief.text.strip()
    }
    fallback = {
        brief.section: brief for brief in heuristic_section_briefs(ranked, config, loc)
    }
    out: list[SectionBrief] = []
    for section in SECTIONS:
        items = section_items(ranked, section)
        if not items:
            continue
        brief = by_section.get(section) or fallback[section]
        ref_uids = {ref.uid for ref in brief.refs}
        coverage = list(brief.coverage_refs)
        coverage_uids = {ref.uid for ref in coverage}
        for index, item in items:
            uid = item.item.id
            if uid not in ref_uids and uid not in coverage_uids:
                coverage.append(_ref_for(ranked, index, loc))
                coverage_uids.add(uid)
        out.append(
            SectionBrief(
                section=section,
                text=truncate_section_brief(brief.text, loc),
                refs=brief.refs,
                coverage_refs=tuple(coverage),
                segments=brief.segments,
            )
        )
    return tuple(out)
