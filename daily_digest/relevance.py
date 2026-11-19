"""Small, dependency-free relevance helpers for feed/news filtering."""

from __future__ import annotations

import re
from collections.abc import Sequence


def matches_topics(title: str, summary: str, topics: Sequence[str]) -> bool:
    """Case-insensitive topic match; 1-3 char tokens use word boundaries.

    Word boundaries keep short terms such as "AI" and "GPU" from matching
    inside unrelated words ("available", "training").
    """
    haystack = f"{title} {summary}".lower()
    for topic in topics:
        needle = topic.strip().lower()
        if not needle:
            continue
        if len(needle) <= 3:
            if re.search(rf"\b{re.escape(needle)}\b", haystack):
                return True
        elif needle in haystack:
            return True
    return False
