"""Locale-native writer prompt fragments.

One shared task skeleton; only style data, examples, and anti-patterns vary by
locale. This is deliberately not a separate Japanese template.
"""

from __future__ import annotations

from daily_digest.i18n import PROMPT_LANGUAGE, normalize_locale

STYLE_CARDS = {
    "vi": (
        "Viết như một biên tập viên bản tin kỹ thuật sắc gọn. Nêu kết quả cụ thể "
        "trước, dùng câu chủ động, đưa ít nhất một con số hoặc tên phương pháp, "
        "và nói rõ vì sao người đọc quan tâm. Tránh 'bài báo này' và các câu "
        "chung chung."
    ),
    "en": (
        "Write like a sharp technical newsletter editor. Lead with the concrete "
        "result, use active voice, include at least one number or named method, "
        "and state why this reader cares. Never open with 'This paper proposes/"
        "presents/introduces'. Avoid 'novel', 'leverage', and 'significant'."
    ),
    "ja": (
        "技術ニュースの敏腕編集者のように、具体的な結果から書いてください。"
        "能動的な表現で、数字や手法名を少なくとも一つ入れ、読者にとっての意味を"
        "明示してください。文はです・ます調。モデル名・データセット名はラテン"
        "文字のままで構いません。"
    ),
}

ANTI_PATTERNS = {
    "vi": (
        "Không mở bằng 'Bài báo này...'.",
        "Không dùng 'đề xuất một phương pháp mới' mà không nêu kết quả.",
        "Không lặp lại title.",
    ),
    "en": (
        "Do not write 'This paper proposes/presents/introduces...'.",
        "Do not use 'novel', 'leverage', or 'significant'.",
        "Do not repeat the title or write a generic one-line abstract.",
    ),
    "ja": (
        "「本論文では」で始めないでください。",
        "「革新的」「可能性がある」などの曖昧な表現を避けてください。",
        "タイトルをそのまま繰り返さないでください。",
    ),
}

ITEM_EXAMPLES = {
    "vi": (
        "Ví dụ: 'Giảm 23% chi phí decode ở ngữ cảnh dài bằng scorer KV nhẹ; "
        "đáng thử nếu đang tối ưu serving.'",
    ),
    "en": (
        "Example: 'Cuts decode cost by 23% on long-context serving with a "
        "lightweight KV scorer; worth testing if you run inference.'",
    ),
    "ja": (
        "例: 「軽量なKVスコアラで長文推論のデコードコストを23%削減。servingを"
        "運用しているなら試す価値があります。」",
    ),
}

OVERVIEW_EXAMPLES = {
    "vi": (
        "Ví dụ: 'Hai hướng nổi bật: tối ưu inference bằng cache/scorer và "
        "đánh giá agent bằng benchmark nhỏ. Điểm cần nhớ: ...'",
    ),
    "en": (
        "Example: 'Two threads stand out: inference optimized by cache/scorer "
        "work, and agent evaluation moving toward small reproducible benchmarks. "
        "Key takeaway: ...'",
    ),
    "ja": (
        "例: 「推論の最適化と、小規模で再現可能なエージェント評価の二つが"
        "目立ちます。要点: ...」",
    ),
}


def _loc(locale: str) -> str:
    return normalize_locale(locale) or "vi"


def item_summary_limit(config_max_words: int, locale: str) -> str:
    if _loc(locale) == "ja":
        return "150-220 Japanese characters"
    return f"45-70 words, never exceed {config_max_words}"


def overview_target_range(item_count: int, locale: str) -> tuple[int, int]:
    if _loc(locale) == "ja":
        return (500, 900) if item_count <= 12 else (900, 1400)
    return (700, 1200) if item_count <= 12 else (1200, 2000)


def item_system_prompt(
    locale: str, *, topics: str, reader_context: str, limit: str
) -> str:
    loc = _loc(locale)
    context = f"\nReader context: {reader_context}" if reader_context else ""
    return (
        f"You write concise per-item summaries for a daily AI/tech digest. "
        f"Reader interests: {topics}.{context}\n"
        f"{STYLE_CARDS[loc]}\n"
        f"Length: {limit}. Two or three sentences. One concrete method/result/"
        f"number and one sentence on practical relevance.\n"
        f"Write in {PROMPT_LANGUAGE[loc]}.\n"
        + "\n".join(ANTI_PATTERNS[loc])
        + "\n"
        + "\n".join(ITEM_EXAMPLES[loc])
        + "\nRespond with ONLY a JSON object:\n"
        '{"items": [{"id": <absolute item number>, "summary": "<summary>"}]}'
    )


def overview_system_prompt(
    locale: str,
    *,
    topics: str,
    reader_context: str,
    target: tuple[int, int],
    hard_cap: int,
    takeaway: str,
    item_count: int,
) -> str:
    loc = _loc(locale)
    context = f"\nReader context: {reader_context}" if reader_context else ""
    low, high = target
    point_range = "3-5" if item_count >= 20 else "2-4"
    return (
        f"You write the day overview for a daily AI/tech digest. "
        f"Reader interests: {topics}.{context}\n"
        f"{STYLE_CARDS[loc]}\n"
        f"Synthesize the main themes across the selected items. Write "
        f"{point_range} short points separated by blank lines. Each point must "
        f"cite at least two different items; never spend a whole point on one "
        f"item. Cite only the 3-6 most important items using [[n]] in place "
        f"of the title. Do not enumerate every item. End with one point "
        f"starting with '{takeaway}'. Target {low}-{high} characters, hard "
        f"cap {hard_cap}. "
        f"Write in {PROMPT_LANGUAGE[loc]}.\n"
        + "\n".join(ANTI_PATTERNS[loc])
        + "\n"
        + "\n".join(OVERVIEW_EXAMPLES[loc])
        + "\nRespond with ONLY a JSON object:\n"
        '{"overview": "<overview>"}'
    )


def section_briefs_system_prompt(
    locale: str, *, topics: str, reader_context: str, cap: int
) -> str:
    loc = _loc(locale)
    context = f"\nReader context: {reader_context}" if reader_context else ""
    return (
        f"You write short section briefings for a daily AI/tech digest. "
        f"Reader interests: {topics}.{context}\n"
        f"{STYLE_CARDS[loc]}\n"
        "Write one briefing for EACH section that has items: papers, tech_news, "
        "tools_releases. Three to five sentences, at most "
        f"{cap} characters. Cover the strongest concrete results or releases "
        "across the section, not only the first item, and say what connects "
        "the rest. Do not repeat item titles verbatim. Cite at most three items "
        "per section using their absolute item numbers in refs.\n"
        f"Write every briefing in {PROMPT_LANGUAGE[loc]}.\n"
        + "\n".join(ANTI_PATTERNS[loc])
        + "\nRespond with ONLY a JSON object:\n"
        '{"sections": [{"section": "papers", "text": "<briefing>", '
        '"refs": [<absolute item numbers>]}]}'
    )
