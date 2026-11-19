"""Ranking entry point: LLM first, heuristic fallback — the digest always gets ranked."""

from __future__ import annotations

from daily_digest.config import Config
from daily_digest.model import Item, RankedItem
from daily_digest.ranking.heuristic import rank_heuristic
from daily_digest.ranking.diversify import diversify_tech_news
from daily_digest.ranking.llm import LlmClient, LlmError, rank_with_llm
from daily_digest.util import LOG


def select(
    items: list[Item],
    llm_client: LlmClient | None,
    config: Config,
    reader_context: str = "",
    adjustments: dict[str, float] | None = None,
) -> tuple[list[RankedItem], str]:
    """Returns (ranked_items, mode) where mode is "llm" or "heuristic"."""
    if llm_client is not None and items:
        try:
            ranked = rank_with_llm(items, llm_client.chat, config, reader_context)[
                : config.llm.top_n
            ]
            if config.llm.diversify_tech_news:
                ranked = diversify_tech_news(ranked, items, config, adjustments)
            LOG.info("LLM ranking OK: %d items via %s", len(ranked), config.llm.model)
            return ranked, "llm"
        except LlmError as exc:
            LOG.warning("LLM ranking failed, using heuristic fallback: %s", exc)
    ranked = rank_heuristic(items, config, adjustments)[: config.llm.top_n]
    if config.llm.diversify_tech_news:
        ranked = diversify_tech_news(ranked, items, config, adjustments)
    return ranked, "heuristic"
