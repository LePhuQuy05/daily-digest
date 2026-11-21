"""Writer-quality metrics must separate specific localized output from generic."""

from __future__ import annotations

import json
from pathlib import Path

from daily_digest.writer_quality import (
    compare_scores,
    fits_visible,
    generic_hits,
    is_specific,
    locale_match,
    score_payload,
    summarize_items,
)

FIXTURES = Path(__file__).parent / "fixtures" / "quality"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_specificity_and_generic_patterns():
    assert is_specific("The method cuts latency by 23%.")
    assert is_specific("Qwen2.5-7B improves tool use.")
    assert not is_specific("This paper proposes a novel approach.")
    assert generic_hits("This paper proposes a novel approach.", "en") >= 2
    assert generic_hits("本論文では革新的な手法を提案する。", "ja") >= 1


def test_locale_detection():
    assert locale_match("これは日本語の要約です。", "ja")
    assert not locale_match("This is an English summary.", "ja")
    assert locale_match("Đây là bản tóm tắt tiếng Việt.", "vi")
    assert not locale_match("This is an English summary.", "vi")
    assert locale_match("This is an English summary.", "en")


def test_visible_budget_rejects_tail_cut():
    assert fits_visible("short summary", "en")
    assert not fits_visible("x" * 500, "en")


def test_good_and_bad_fixtures_discriminate():
    good = score_payload(_load("good_en.json"))
    bad = score_payload(_load("bad_en.json"))
    assert good["passes"] is True
    assert bad["passes"] is False
    assert good["specificity_ratio"] > bad["specificity_ratio"]
    assert good["generic_ratio"] < bad["generic_ratio"]
    assert good["points"] > bad["points"]


def test_ja_fixture_requires_kana_and_japanese():
    good = score_payload(_load("good_ja.json"))
    bad = score_payload(_load("bad_ja.json"))
    assert good["passes"] is True
    assert bad["passes"] is False
    assert good["locale_match_ratio"] == 1.0
    assert bad["locale_match_ratio"] == 0.0


def test_summary_metrics_ignore_empty_summaries():
    metrics = summarize_items(
        [{"llm_summary": "23% faster."}, {"llm_summary": ""}],
        "en",
    )
    assert metrics.count == 2
    assert metrics.with_summary == 1
    assert metrics.average_chars > 0


def test_compare_scores_reports_deltas():
    current = {"specificity_ratio": 0.9, "generic_ratio": 0.1}
    baseline = {"specificity_ratio": 0.7, "generic_ratio": 0.2}
    delta = compare_scores(current, baseline)
    assert delta["specificity_ratio"] == 0.2
    assert delta["generic_ratio"] == -0.1
