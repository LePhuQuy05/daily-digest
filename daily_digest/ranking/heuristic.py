"""Heuristic ranking: interest-keyword hits + popularity + recency. Always available fallback."""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone

from daily_digest.config import Config
from daily_digest.model import Item, RankedItem, Section

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

_TOOLS_RE = re.compile(
    r"\b(release[sd]?|launch(?:es|ed)?|open[- ]sourc(?:e|ed)|announc(?:e|es|ed)|v[0-9]+\.[0-9]+|beta|is now|GA)\b",
    re.IGNORECASE,
)


def default_section(item: Item) -> Section:
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
    from daily_digest.rules import always_match

    if always_match(item, config.interests.always):
        score += ALWAYS_BONUS
    if item.published:
        age_hours = (datetime.now(timezone.utc) - item.published).total_seconds() / 3600
        if 0 <= age_hours <= FRESH_HOURS:
            score += FRESH_BONUS
    return score


def _why_line(item: Item, topics: list[str]) -> str:
    bits: list[str] = []
    hits = topic_hits(item, topics)
    if hits:
        bits.append("matches: " + ", ".join(hits[:3]))
    if item.points:
        bits.append(f"{item.points} pts")
    if item.citations:
        bits.append(f"{item.citations} citations")
    if item.source == "hf_papers":
        bits.append("trending on HF Papers")
    elif item.source == "alphaxiv":
        bits.append("hot on alphaXiv")
    elif item.source == "emergentmind":
        bits.append("trending across social media (Emergent Mind)")
    elif item.source == "arxiv":
        bits.append(f"new arXiv {item.id.removeprefix('arxiv:')}")
    else:
        bits.append("HN front page")
    return " · ".join(bits) if bits else "top story today"


def rank_heuristic(
    items: list[Item], config: Config, adjustments: dict[str, float] | None = None
) -> list[RankedItem]:
    """Deterministic ranking + a mechanical 'why' line so the digest never renders empty reasons."""
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
                why=_why_line(item, config.interests.topics)[:140],
                section=section,
            )
        )
    return ranked


def heuristic_order(
    items: list[Item], config: Config, adjustments: dict[str, float] | None = None
) -> list[Item]:
    """Order-only view, used to pre-cap the candidate pool before the LLM sees it."""
    return [ranked.item for ranked in rank_heuristic(items, config, adjustments)]


_OVERVIEW_LABELS = {"vi": "Tổng hợp hôm nay", "en": "Today's overview"}
_OVERVIEW_TEMPLATES = {
    "vi": "{total} mục hôm nay: {papers} papers · {news} tin công nghệ · {tools} tools. Chủ đề nổi bật: {topics}.",
    "en": "{total} items today: {papers} papers · {news} tech news · {tools} tools. Top themes: {topics}.",
}


def overview_label(config: Config) -> str:
    return _OVERVIEW_LABELS.get(
        config.llm.overview_language.strip().lower(), "Today's overview"
    )


def heuristic_overview(ranked: list[RankedItem], config: Config) -> str:
    """Mechanical day-overview fallback (always available, no LLM): counts + top themes."""
    language = config.llm.overview_language.strip().lower()
    template = _OVERVIEW_TEMPLATES.get(language, _OVERVIEW_TEMPLATES["en"])
    papers = sum(1 for r in ranked if r.section == "papers")
    news = sum(1 for r in ranked if r.section == "tech_news")
    tools = sum(1 for r in ranked if r.section == "tools_releases")

    theme_counts: dict[str, int] = {}
    for ranked_item in ranked:
        for topic in topic_hits(ranked_item.item, config.interests.topics):
            theme_counts[topic] = theme_counts.get(topic, 0) + 1
    top_themes = sorted(theme_counts, key=theme_counts.get, reverse=True)[:3]
    topics = ", ".join(top_themes) if top_themes else "—"
    return template.format(
        total=len(ranked), papers=papers, news=news, tools=tools, topics=topics
    )
