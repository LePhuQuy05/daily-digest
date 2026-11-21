"""Generated content and Japanese text handling per locale."""

from __future__ import annotations

from daily_digest.model import RankedItem
from daily_digest.overview import (
    ensure_coverage,
    parse_overview,
    short_label,
)
from daily_digest.ranking.heuristic import rank_heuristic
from daily_digest.ranking.llm import (
    MAX_WHY_JA,
    _validate_summaries,
    overview_char_budget,
    rank_with_llm,
    summarize_with_llm,
)
from helpers import FakeChat, llm_ok_json, make_config, make_item


def _items():
    return [
        make_item(
            id="arxiv:2611.00001",
            title="A paper about LLM agents",
            url="https://arxiv.org/abs/2611.00001",
            source="arxiv",
            summary="We study agents.",
        )
    ]


def test_editor_prompt_uses_selected_language(tmp_path):
    config = make_config(tmp_path)
    for locale, word in (("vi", "Vietnamese"), ("en", "English"), ("ja", "Japanese")):
        chat = FakeChat(llm_ok_json(1))
        rank_with_llm(_items(), chat, config, locale=locale)
        system = chat.calls[0][0]["content"]
        assert f'Write each "why" in {word}.' in system
        assert (
            "under 80 characters" in system
            if locale == "ja"
            else "under 140 characters" in system
        )


def test_japanese_why_is_capped(tmp_path):
    config = make_config(tmp_path)
    response = (
        '{"selected": [{"id": 0, "why": "' + "あ" * 200 + '", "section": "papers"}]}'
    )
    ranked = rank_with_llm(_items(), FakeChat(response), config, locale="ja")
    assert len(ranked[0].why) <= MAX_WHY_JA


def test_writer_prompt_uses_japanese_marker_and_limit(tmp_path):
    config = make_config(tmp_path)
    chat = FakeChat(
        '{"overview": "本日は[[0]]が重要です。要点: 続きを読みましょう。", '
        '"items": [{"id": 0, "summary": "これは日本語の要約です。"}]}'
    )
    out, overview = summarize_with_llm(
        rank_with_llm(_items(), FakeChat(llm_ok_json(1)), config, locale="ja"),
        chat,
        config,
        locale="ja",
    )
    system = chat.calls[0][0]["content"]
    assert "Write the overview in Japanese" in system
    assert "at most 180 Japanese characters" in system
    assert "要点:" in system
    assert "Điểm cần nhớ" not in system
    assert overview.startswith("本日は")
    assert out[0].llm_summary == "これは日本語の要約です。"


def test_kana_gate_rejects_long_english_output():
    ranked = rank_with_llm(
        _items(),
        FakeChat(llm_ok_json(1)),
        make_config(__import__("pathlib").Path(".")),
        locale="ja",
    )
    payload = {
        "items": [
            {"id": 0, "summary": "This is a long English summary without any kana."}
        ]
    }
    assert _validate_summaries(payload, {0: ranked[0]}, "ja") == {}


def test_overview_budget_by_locale():
    assert overview_char_budget(30, "vi") == 2680
    assert overview_char_budget(30, "en") == 2680
    assert overview_char_budget(30, "ja") == 1800


def test_japanese_fullwidth_markers_and_marker_takeaway():
    ranked = [
        make_item(
            id=f"arxiv:2611.{i:05d}",
            title=f"論文{i}：とても長い日本語のタイトルがここに続きます",
            url=f"https://arxiv.org/abs/2611.{i:05d}",
            source="arxiv",
        )
        for i in range(2)
    ]
    ranked = [RankedItem(item=item, why="why", section="papers") for item in ranked]
    points = parse_overview(
        "［［0］］と［［1］］が重要です。\n\n要点: 明日も続きます。",
        ranked,
        "ja",
    )
    assert [point.kind for point in points] == ["theme", "takeaway"]
    covered = ensure_coverage(points, ranked, "ja")
    assert {
        segment.ref.uid
        for point in covered
        for segment in point.segments
        if segment.ref
    } == {item.item.id for item in ranked}
    text = "".join(segment.text for point in covered for segment in point.segments)
    assert "[[" not in text and "］" not in text
    label = short_label("非常に長い日本語のタイトル：続き", 1, "ja")
    assert len(label) <= 14


def test_japanese_heuristic_why_is_localized(tmp_path):
    config = make_config(tmp_path)
    item = _items()[0]
    ranked = rank_heuristic([item], config, locale="ja")
    assert "新着arXiv" in ranked[0].why
    assert "new arXiv" not in ranked[0].why
