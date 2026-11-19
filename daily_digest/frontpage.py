"""Front-page layout model: pure, no Jinja/template dependencies.

The view never re-ranks: `ranked` is already sorted by the ranking layer. This
module only partitions it into a hero, content-aware section fronts, a "most
read" list of anchor links, and source counts for the rail.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from daily_digest.model import SECTIONS, SECTION_TITLES, RankedItem, Section


@dataclass(frozen=True)
class SectionFront:
    key: Section
    title: str
    lead: RankedItem | None
    briefs: tuple[RankedItem, ...]
    total: int  # total in the section, including the hero when it came from here


@dataclass(frozen=True)
class FrontPage:
    lead: RankedItem | None
    secondary: RankedItem | None
    sections: tuple[SectionFront, ...]  # all sections, SECTIONS order
    most_read: tuple[RankedItem, ...]  # ranked[2:5], anchor links only
    source_counts: dict[str, int]  # raw source keys for the rail


def build_front_page(ranked: Sequence[RankedItem]) -> FrontPage:
    """Partition an already-ranked digest into the front-page layout.

    Every item appears exactly once: lead, secondary, section lead, or section
    brief. `most_read` is a subset rendered as links back to those story anchors,
    not as duplicate cards (duplicating them would duplicate feedback buttons).
    """
    items = tuple(ranked)
    lead = items[0] if items else None
    secondary = items[1] if len(items) > 1 else None

    sections: list[SectionFront] = []
    for key in SECTIONS:
        in_section = [item for item in items if item.section == key]
        remaining = [
            item for item in in_section if item is not lead and item is not secondary
        ]
        sections.append(
            SectionFront(
                key=key,
                title=SECTION_TITLES[key],
                lead=remaining[0] if remaining else None,
                briefs=tuple(remaining[1:]),
                total=len(in_section),
            )
        )

    return FrontPage(
        lead=lead,
        secondary=secondary,
        sections=tuple(sections),
        most_read=tuple(items[2:5]),
        source_counts=dict(Counter(item.item.source for item in items)),
    )
