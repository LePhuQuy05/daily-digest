"""Heuristic ranking: interest-keyword hits + popularity + recency. Always available fallback."""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone

from daily_digest.config import Config
from daily_digest.i18n import normalize_locale, t
from daily_digest.model import Item, RankedItem, Section
from daily_digest.relevance import matches_topics
from daily_digest.source_labels import labels_for

TOPIC_BONUS = 2.0
HF_TRENDING_BONUS = 1.5  # human-curated signal
ALPHAXIV_TRENDING_BONUS = 1.0  # community upvotes (counts also feed the points term)
EM_TRENDING_BONUS = (
    1.0  # cross-platform social attention signal (weaker: no counts in RSS)
)
CITATION_BONUS_SCALE = (
    0.5  # 0.5*log10(1+citations): modest, most pool papers are days old
)
ALWAYS_BONUS = 3.0  # F5: reader's explicit must-see keyword
ADJUSTMENT_ITEM_CLAMP = 1.5  # F1: item-level bound on summed feedback adjustments
FRESH_HOURS = 24.0
FRESH_BONUS = 1.0
# Curated first-party/analysis feeds are more trustworthy than an unvetted
# front-page link; the bonus makes them competitive without overriding topics.
SOURCE_QUALITY_BONUS = {
    "openai_news": 1.8,
    "deepmind_blog": 1.8,
    "google_ai_blog": 1.6,
    "google_research": 1.4,
    "microsoft_research": 1.4,
    "huggingface_blog": 1.4,
    "the_verge_ai": 1.0,
    "ieee_spectrum_ai": 1.0,
    "ars_technica": 1.0,
    "mit_tech_review": 1.0,
    "simon_willison": 1.3,
    "interconnects": 1.3,
    "import_ai": 1.3,
}
RELEASE_SOURCE_BONUS = 0.8

_TOOLS_RE = re.compile(
    r"\b(release[sd]?|launch(?:es|ed)?|open[- ]sourc(?:e|ed)|announc(?:e|es|ed)|v[0-9]+\.[0-9]+|beta|is now|GA)\b",
    re.IGNORECASE,
)


def default_section(item: Item) -> Section:
    if item.section_hint:
        return item.section_hint
    return (
        "papers"
        if item.source in ("arxiv", "hf_papers", "emergentmind", "alphaxiv")
        else "tech_news"
    )


def topic_hits(item: Item, topics: list[str]) -> list[str]:
    text = f"{item.title} {item.summary}".lower()
    return [topic for topic in topics if topic.lower() in text]


def score_item(
    item: Item, config: Config, adjustments: dict[str, float] | None = None
) -> float:
    """adjustments: per-topic feedback deltas (F1). The SUM over this item's topic
    hits is clamped at ±ADJUSTMENT_ITEM_CLAMP — bounded per ITEM, not per topic,
    so many overlapping liked topics cannot compound unboundedly."""
    score = len(topic_hits(item, config.interests.topics)) * TOPIC_BONUS
    if adjustments:
        total_adjustment = sum(
            adjustments.get(topic, 0.0)
            for topic in topic_hits(item, config.interests.topics)
        )
        score += max(
            -ADJUSTMENT_ITEM_CLAMP, min(ADJUSTMENT_ITEM_CLAMP, total_adjustment)
        )
    if item.points:
        score += math.log10(item.points + 1)
    if item.citations:
        score += CITATION_BONUS_SCALE * math.log10(item.citations + 1)
    score += config.interests.weights.get(default_section(item), 1.0)
    if item.source == "hf_papers":
        score += HF_TRENDING_BONUS
    elif item.source == "alphaxiv":
        score += ALPHAXIV_TRENDING_BONUS
    elif item.source == "emergentmind":
        score += EM_TRENDING_BONUS
    if item.source.startswith("gh_"):
        score += RELEASE_SOURCE_BONUS
    else:
        score += SOURCE_QUALITY_BONUS.get(item.source, 0.0)
    from daily_digest.rules import always_match

    if always_match(item, config.interests.always):
        score += ALWAYS_BONUS
    if item.published:
        age_hours = (datetime.now(timezone.utc) - item.published).total_seconds() / 3600
        if 0 <= age_hours <= FRESH_HOURS:
            score += FRESH_BONUS
    return score


def _why_line(
    item: Item,
    topics: list[str],
    labels: dict[str, str] | None = None,
    locale: str = "vi",
) -> str:
    loc = normalize_locale(locale) or "vi"
    bits: list[str] = []
    hits = topic_hits(item, topics)
    if hits:
        bits.append(t(loc, "heuristic_matches").format(topics=", ".join(hits[:3])))
    if item.points:
        bits.append(t(loc, "story_points").format(n=item.points))
    if item.citations:
        bits.append(t(loc, "story_citations").format(n=item.citations))
    if item.source == "hf_papers":
        bits.append(t(loc, "heuristic_trending_hf"))
    elif item.source == "alphaxiv":
        bits.append(t(loc, "heuristic_trending_alphaxiv"))
    elif item.source == "emergentmind":
        bits.append(t(loc, "heuristic_trending_em"))
    elif item.source == "arxiv":
        bits.append(
            t(loc, "heuristic_new_arxiv").format(id=item.id.removeprefix("arxiv:"))
        )
    elif item.source == "hn":
        bits.append(t(loc, "heuristic_hn"))
    elif item.source.startswith("gh_"):
        bits.append(t(loc, "heuristic_release"))
    else:
        label = (labels or {}).get(item.source, item.source)
        bits.append(t(loc, "heuristic_via").format(label=label))
    return " · ".join(bits) if bits else t(loc, "heuristic_top")


def heuristic_why(item: Item, config: Config, locale: str = "vi") -> str:
    """Expose the deterministic why line for localization fallbacks."""
    loc = normalize_locale(locale) or "vi"
    limit = 80 if loc == "ja" else 140
    return _why_line(item, config.interests.topics, labels_for(config), loc)[:limit]


def rank_heuristic(
    items: list[Item],
    config: Config,
    adjustments: dict[str, float] | None = None,
    locale: str = "vi",
) -> list[RankedItem]:
    """Deterministic ranking + a mechanical 'why' line so the digest never renders empty reasons."""
    labels = labels_for(config)
    ordered = sorted(
        items, key=lambda item: score_item(item, config, adjustments), reverse=True
    )
    ranked: list[RankedItem] = []
    for item in ordered:
        section = default_section(item)
        if section == "tech_news" and _TOOLS_RE.search(item.title):
            section = "tools_releases"
        ranked.append(
            RankedItem(
                item=item,
                why=_why_line(item, config.interests.topics, labels, locale)[:140],
                section=section,
            )
        )
    return ranked


def heuristic_order(
    items: list[Item],
    config: Config,
    adjustments: dict[str, float] | None = None,
    locale: str = "vi",
) -> list[Item]:
    """Order-only view, used to pre-cap the candidate pool before the LLM sees it."""
    return [
        ranked.item for ranked in rank_heuristic(items, config, adjustments, locale)
    ]


def balanced_pool(
    items: list[Item],
    config: Config,
    cap: int,
    adjustments: dict[str, float] | None = None,
    locale: str = "vi",
) -> list[Item]:
    """Pre-cap the editor pool while reserving space for news and tool releases.

    A pure score cut is paper-dominated (papers earn topic hits, citations and
    source weight), so the LLM never sees enough news/tool candidates to fill
    those sections. Quotas guarantee the editor has a real choice; leftover
    slots still go to the best remaining items.
    """
    ranked = rank_heuristic(items, config, adjustments, locale)
    # HN is a general front page: keep only AI-relevant links in the editorial
    # pool, otherwise high-score off-topic stories crowd out lab/press feeds.
    ranked = [
        ranked_item
        for ranked_item in ranked
        if ranked_item.item.source != "hn"
        or matches_topics(
            ranked_item.item.title,
            ranked_item.item.summary,
            config.sources.feeds.topics,
        )
    ]
    by_section: dict[Section, list[Item]] = {
        "papers": [],
        "tech_news": [],
        "tools_releases": [],
    }
    for ranked_item in ranked:
        by_section[ranked_item.section].append(ranked_item.item)

    news_quota = min(len(by_section["tech_news"]), max(8, cap * 20 // 100))
    tools_quota = min(len(by_section["tools_releases"]), max(5, cap * 12 // 100))
    paper_quota = max(0, cap - news_quota - tools_quota)

    chosen: set[int] = set()
    for section_items, quota in (
        (by_section["papers"], paper_quota),
        (by_section["tech_news"], news_quota),
        (by_section["tools_releases"], tools_quota),
    ):
        for item in section_items[:quota]:
            chosen.add(id(item))

    for ranked_item in ranked:
        if len(chosen) >= cap:
            break
        chosen.add(id(ranked_item.item))

    return [
        ranked_item.item for ranked_item in ranked if id(ranked_item.item) in chosen
    ]


def overview_label(locale: str = "vi") -> str:
    return t(locale, "overview_label")


def heuristic_overview(
    ranked: list[RankedItem], config: Config, locale: str = "vi"
) -> str:
    """Mechanical day-overview fallback (always available, no LLM): counts + top themes."""
    loc = normalize_locale(locale) or "vi"
    papers = sum(1 for r in ranked if r.section == "papers")
    news = sum(1 for r in ranked if r.section == "tech_news")
    tools = sum(1 for r in ranked if r.section == "tools_releases")

    theme_counts: dict[str, int] = {}
    for ranked_item in ranked:
        for topic in topic_hits(ranked_item.item, config.interests.topics):
            theme_counts[topic] = theme_counts.get(topic, 0) + 1
    top_themes = sorted(theme_counts, key=theme_counts.get, reverse=True)[:3]
    topics = ", ".join(top_themes) if top_themes else "—"
    return t(loc, "heuristic_overview").format(
        total=len(ranked), papers=papers, news=news, tools=tools, topics=topics
    )
