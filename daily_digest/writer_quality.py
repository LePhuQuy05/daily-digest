"""Offline writer-quality metrics for vi/en/ja digest editions.

These are deliberately simple, deterministic, and dependency-free. They are a
regression gate, not a substitute for blind human review.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from daily_digest.i18n import has_kana, normalize_locale

VISIBLE_LINES = {
    "vi": 6,
    "en": 6,
    "ja": 6,
}
CHARS_PER_LINE = {
    "vi": 78,
    "en": 78,
    "ja": 42,
}
GENERIC_PATTERNS = {
    "vi": (
        r"\bbài báo này\b",
        r"\bnghiên cứu này\b",
        r"\bđề xuất\b",
        r"\bcó thể\b",
    ),
    "en": (
        r"\bthis paper (proposes|presents|introduces|studies)\b",
        r"\bnovel\b",
        r"\bleverage\b",
        r"\bsignificant(ly)?\b",
    ),
    "ja": (
        "本論文では",
        "本稿では",
        "革新的",
        "可能性がある",
        "重要である",
    ),
}
VI_CHARS = re.compile(
    r"[ăâđêôơưĂÂĐÊÔƠƯáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]"
)
TECH_TOKEN = re.compile(
    r"\b(?=[A-Za-z0-9_.:+-]*\d)[A-Za-z0-9_.:+-]{2,}\b"
    r"|\b[A-Za-z]+[-_][A-Za-z0-9]+\b"
)
NUMBER = re.compile(r"\d")
KANA = re.compile(r"[\u3040-\u30ff\u31f0-\u31ff]")
NUMBER_FACT = re.compile(r"\d+(?:[.,]\d+)?\s*(?:%|x|\u00d7|B|M|K|GB|ms|s)?")
NAME_FACT = re.compile(r"\b(?:[A-Z]{2,}[A-Za-z0-9-]*|[A-Za-z]+\d[A-Za-z0-9.-]*)\b")
FACT_STOPWORDS = {
    "THE",
    "THIS",
    "THAT",
    "THESE",
    "THOSE",
    "AND",
    "FOR",
    "WITH",
    "FROM",
    "FIGURE",
    "TABLE",
    "SECTION",
    "APPENDIX",
}


@dataclass(frozen=True)
class SummaryMetrics:
    locale: str
    count: int
    with_summary: int
    average_chars: float
    specificity_ratio: float
    generic_ratio: float
    locale_match_ratio: float
    visible_fit_ratio: float
    fact_recall_ratio: float


def _text(value: object) -> str:
    return " ".join(str(value or "").split())


def locale_match(text: str, locale: str) -> bool:
    loc = normalize_locale(locale) or "vi"
    if not text:
        return False
    if loc == "ja":
        return bool(KANA.search(text))
    if loc == "vi":
        return bool(VI_CHARS.search(text))
    return bool(re.search(r"[A-Za-z]", text)) and not bool(KANA.search(text))


def is_specific(text: str) -> bool:
    return bool(NUMBER.search(text) or TECH_TOKEN.search(text))


def generic_hits(text: str, locale: str) -> int:
    loc = normalize_locale(locale) or "vi"
    return sum(
        1
        for pattern in GENERIC_PATTERNS[loc]
        if re.search(pattern, text, re.IGNORECASE)
    )


def visible_char_budget(locale: str, lines: int | None = None) -> int:
    loc = normalize_locale(locale) or "vi"
    return (lines or VISIBLE_LINES[loc]) * CHARS_PER_LINE[loc]


def fits_visible(text: str, locale: str, lines: int | None = None) -> bool:
    return len(_text(text)) <= visible_char_budget(locale, lines)


def _number_fact(token: str) -> str:
    raw = token.replace(" ", "").lower().replace(",", ".")
    match = re.match(r"\d+(?:\.\d+)?", raw)
    if match is None:
        return ""
    core = match.group(0)
    unit = raw[match.end() :]
    # Years and lone digits are too weak to prove the summary kept a fact.
    if core.isdigit() and len(core) == 4 and 1900 <= int(core) <= 2100:
        return ""
    if len(core.replace(".", "")) < 2 and not unit:
        return ""
    return core


def source_facts(text: str) -> set[str]:
    """Extract must-mention numbers, or named methods when no numbers exist."""
    value = _text(text)
    numbers = {
        fact
        for match in NUMBER_FACT.finditer(value)
        if (fact := _number_fact(match.group(0)))
    }
    if numbers:
        return numbers
    return {
        match.group(0).lower()
        for match in NAME_FACT.finditer(value)
        if match.group(0).upper() not in FACT_STOPWORDS and len(match.group(0)) >= 3
    }


def retains_source_fact(source: str, summary: str) -> bool:
    facts = source_facts(source)
    if not facts:
        return True
    compact = _text(summary).lower().replace(" ", "")
    return any(fact in compact for fact in facts)


def summarize_items(items: list[dict[str, Any]], locale: str) -> SummaryMetrics:
    loc = normalize_locale(locale) or "vi"
    present_pairs = [
        (_text(item.get("summary")), _text(item.get("llm_summary")))
        for item in items
        if _text(item.get("llm_summary"))
    ]
    present = [summary for _, summary in present_pairs]
    count = len(items)
    return SummaryMetrics(
        locale=loc,
        count=count,
        with_summary=len(present),
        average_chars=(sum(len(text) for text in present) / len(present))
        if present
        else 0.0,
        specificity_ratio=(sum(is_specific(text) for text in present) / len(present))
        if present
        else 0.0,
        generic_ratio=(sum(generic_hits(text, loc) for text in present) / len(present))
        if present
        else 0.0,
        locale_match_ratio=(
            sum(locale_match(text, loc) for text in present) / len(present)
        )
        if present
        else 0.0,
        visible_fit_ratio=(
            sum(fits_visible(text, loc) for text in present) / len(present)
        )
        if present
        else 0.0,
        fact_recall_ratio=(
            sum(
                retains_source_fact(source, summary)
                for source, summary in present_pairs
            )
            / len(present_pairs)
        )
        if present_pairs
        else 0.0,
    )


def _overview_points(payload: dict[str, Any]) -> list[dict[str, Any]]:
    points = payload.get("overview_points") or []
    if isinstance(points, list):
        return [point for point in points if isinstance(point, dict)]
    return []


def overview_metrics(payload: dict[str, Any]) -> dict[str, float | int]:
    points = _overview_points(payload)
    refs = []
    for point in points:
        count = 0
        for segment in point.get("segments", []):
            if isinstance(segment, dict) and isinstance(segment.get("ref"), dict):
                count += 1
        refs.append(count)
    themes = [point for point in points if point.get("kind") == "theme"]
    single_ref = sum(
        1
        for point in themes
        if sum(
            1
            for segment in point.get("segments", [])
            if isinstance(segment, dict) and isinstance(segment.get("ref"), dict)
        )
        == 1
    )
    rest = [count for point, count in zip(points, refs) if point.get("kind") == "rest"]
    return {
        "points": len(points),
        "theme_points": len(themes),
        "rest_points": len(rest),
        "max_rest_refs": max(rest, default=0),
        "single_ref_ratio": (single_ref / len(themes)) if len(themes) > 1 else 0.0,
    }


def score_payload(payload: dict[str, Any]) -> dict[str, Any]:
    locale = normalize_locale(payload.get("locale")) or "vi"
    items = payload.get("ranked") or payload.get("items") or []
    if isinstance(items, dict):
        items = list(items.values())
    normalized_items = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("item"), dict):
            normalized_items.append(
                {
                    **item["item"],
                    "why": item.get("why", ""),
                    "llm_summary": item.get("llm_summary", ""),
                }
            )
        else:
            normalized_items.append(item)
    summary = summarize_items(normalized_items, locale)
    overview = overview_metrics(payload)
    score = {
        "locale": locale,
        "items": summary.count,
        "with_summary": summary.with_summary,
        "average_chars": round(summary.average_chars, 1),
        "specificity_ratio": round(summary.specificity_ratio, 3),
        "generic_ratio": round(summary.generic_ratio, 3),
        "locale_match_ratio": round(summary.locale_match_ratio, 3),
        "visible_fit_ratio": round(summary.visible_fit_ratio, 3),
        "fact_recall_ratio": round(summary.fact_recall_ratio, 3),
        **overview,
    }
    score["passes"] = bool(
        score["points"] > 0
        and score["with_summary"] == score["items"]
        and score["fact_recall_ratio"] >= 0.8
        and score["locale_match_ratio"] >= 0.9
        and score["specificity_ratio"] >= 0.8
        and score["generic_ratio"] <= 0.2
        and score["visible_fit_ratio"] >= 0.9
        and score["max_rest_refs"] <= 8
        and score["single_ref_ratio"] <= 0.5
    )
    return score


def score_edition(path: Path) -> dict[str, Any]:
    return score_payload(json.loads(path.read_text(encoding="utf-8")))


def load_snapshot(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def format_score(score: dict[str, Any]) -> str:
    return (
        f"{score['locale']}: items={score['items']} "
        f"summary={score['with_summary']}/{score['items']} "
        f"avg={score['average_chars']} "
        f"specific={score['specificity_ratio']} "
        f"generic={score['generic_ratio']} "
        f"fact={score['fact_recall_ratio']} "
        f"locale={score['locale_match_ratio']} "
        f"visible={score['visible_fit_ratio']} "
        f"points={score['points']} rest={score['max_rest_refs']} "
        f"single={score['single_ref_ratio']} pass={score['passes']}"
    )


def compare_scores(
    current: dict[str, Any], baseline: dict[str, Any]
) -> dict[str, float]:
    keys = (
        "fact_recall_ratio",
        "specificity_ratio",
        "generic_ratio",
        "locale_match_ratio",
        "visible_fit_ratio",
        "max_rest_refs",
        "single_ref_ratio",
    )
    return {
        key: round(float(current.get(key, 0)) - float(baseline.get(key, 0)), 3)
        for key in keys
    }
