"""Editorial diversity guard: at most one tech_news item per source.

The editor LLM sometimes picks two posts from the same publication (e.g. two
Hugging Face blog posts). This guard replaces the LOWER-ranked duplicate with
the best unused tech_news candidate from a different source — but only when
that candidate carries a real description, so a thin vendor post is never used
as padding. Papers and tools_releases are never touched.
"""

from __future__ import annotations

from daily_digest.config import Config
from daily_digest.model import Item, RankedItem
from daily_digest.ranking.heuristic import rank_heuristic
from daily_digest.util import LOG

MIN_REPLACEMENT_SUMMARY_CHARS = 80


def _replacement_candidates(
    pool: list[Item],
    config: Config,
    adjustments: dict[str, float] | None,
    *,
    selected_ids: set[str],
    blocked_sources: set[str],
    locale: str = "vi",
) -> list[RankedItem]:
    """Unused tech_news candidates from other sources, best heuristic score first."""
    return [
        ranked
        for ranked in rank_heuristic(pool, config, adjustments, locale)
        if ranked.section == "tech_news"
        and ranked.item.id not in selected_ids
        and ranked.item.source not in blocked_sources
        and len(ranked.item.summary) >= MIN_REPLACEMENT_SUMMARY_CHARS
    ]


def diversify_tech_news(
    ranked: list[RankedItem],
    pool: list[Item],
    config: Config,
    adjustments: dict[str, float] | None = None,
    *,
    max_per_source: int = 1,
    locale: str = "vi",
) -> list[RankedItem]:
    """Replace duplicate-source tech_news picks with qualified unused candidates.

    Deterministic and logged; keeps item positions (order by importance is
    preserved) and never pads: without a qualified candidate the duplicate stays.
    """
    tech_positions = [
        index for index, item in enumerate(ranked) if item.section == "tech_news"
    ]
    if not tech_positions:
        return ranked

    counts: dict[str, int] = {}
    duplicates: list[int] = []
    for index in tech_positions:
        source = ranked[index].item.source
        counts[source] = counts.get(source, 0) + 1
        if counts[source] > max_per_source:
            duplicates.append(index)
    if not duplicates:
        return ranked

    selected_ids = {ranked_item.item.id for ranked_item in ranked}
    blocked_sources = set(counts)  # every tech source keeps at least one pick
    candidates = _replacement_candidates(
        pool,
        config,
        adjustments,
        selected_ids=selected_ids,
        blocked_sources=blocked_sources,
        locale=locale,
    )

    result = list(ranked)
    replaced = 0
    # Replace the least important duplicates first; the hero/secondary stay.
    for index in reversed(duplicates):
        if not candidates:
            break
        candidate = candidates.pop(0)
        old = result[index]
        result[index] = candidate
        replaced += 1
        LOG.info(
            "diversify: replaced '%s' (%s) with '%s' (%s)",
            old.item.title[:60],
            old.item.source,
            candidate.item.title[:60],
            candidate.item.source,
        )
    if replaced:
        LOG.info("diversify: %d duplicate tech_news source pick(s) replaced", replaced)
    return result
