"""F5 keyword rules: mute (hard drop) and always (strong boost).

Pure functions, enforced at ONE point in the pipeline (post-merge, pre-pool).
Mute beats always. Matching is case-insensitive substring over title+summary.
"""

from __future__ import annotations

from daily_digest.config import Config
from daily_digest.model import Item
from daily_digest.util import LOG

MUTE_WARNING_RATIO = 0.8  # WARN when mute drops more than this share of fresh items


def _match_any(text: str, keywords: list[str]) -> str | None:
    """Return the first keyword that appears (case-insensitively) in text, else None."""
    lowered = text.lower()
    for keyword in keywords:
        if keyword and keyword.lower() in lowered:
            return keyword
    return None


def _haystack(item: Item) -> str:
    return f"{item.title} {item.summary}"


def mute_match(item: Item, mute: list[str]) -> str | None:
    return _match_any(_haystack(item), mute)


def always_match(item: Item, always: list[str]) -> str | None:
    return _match_any(_haystack(item), always)


def apply_mute(
    items: list[Item], config: Config
) -> tuple[list[Item], list[tuple[Item, str]]]:
    """Returns (kept, dropped) where dropped = [(item, matched_keyword)].

    Mute is a HARD drop that beats `always` (an explicitly muted item never
    survives even if it matches an always keyword)."""
    mute = config.interests.mute
    if not mute:
        return items, []
    kept: list[Item] = []
    dropped: list[tuple[Item, str]] = []
    for item in items:
        hit = mute_match(item, mute)
        if hit is not None:
            dropped.append((item, hit))
        else:
            kept.append(item)
    return kept, dropped


def log_mute_summary(
    muted_count: int, kept_count: int, sample_titles: list[str]
) -> None:
    """INFO normally; WARN when mute swallows most of the day (likely over-broad rule)."""
    total = muted_count + kept_count
    if total == 0:
        return
    ratio = muted_count / total
    message = "muted %d/%d fresh items (%.0f%%): %s"
    args = (muted_count, total, ratio * 100, "; ".join(sample_titles[:3]))
    if ratio > MUTE_WARNING_RATIO:
        LOG.warning(message + " — check interests.mute, it may be too broad", *args)
    else:
        LOG.info(message, *args)
