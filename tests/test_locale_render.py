"""Rendered UI chrome follows the selected locale."""

from __future__ import annotations

import json
import re

from daily_digest.model import RankedItem
from daily_digest.render import render_digest
from helpers import make_config, make_item


def _ranked() -> list[RankedItem]:
    paper = make_item(
        id="arxiv:2611.00001",
        title="A paper title",
        url="https://arxiv.org/abs/2611.00001",
        source="arxiv",
    )
    news = make_item(
        id="hn:1",
        title="A news title",
        url="https://example.com/news",
        source="hn",
        points=12,
    )
    return [
        RankedItem(item=paper, why="why", section="papers"),
        RankedItem(item=news, why="why", section="tech_news"),
    ]


def _html(tmp_path, locale: str) -> str:
    config = make_config(tmp_path)
    return render_digest(
        _ranked(),
        date="2026-11-21",
        mode="llm",
        degraded=False,
        sources_failed=[],
        model_name="test-model",
        template=config.template_path,
        overview="A neutral overview.",
        locale=locale,
    )


def _messages(html: str) -> dict:
    match = re.search(
        r'<script type="application/json" id="digest-i18n">(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert match is not None
    return json.loads(match.group(1))


def test_html_lang_and_dates_per_locale(tmp_path):
    vi = _html(tmp_path / "vi", "vi")
    en = _html(tmp_path / "en", "en")
    ja = _html(tmp_path / "ja", "ja")

    assert '<html lang="vi" dir="ltr">' in vi
    assert "THỨ BẢY, 21.11.2026" in vi
    assert '<html lang="en" dir="ltr">' in en
    assert "SATURDAY, 21.11.2026" in en
    assert '<html lang="ja" dir="ltr">' in ja
    assert "2026年11月21日（土）" in ja
    assert 'id="lang-switch"' in ja
    assert 'value="ja" selected' in ja
    assert 'location.href = "demo-" + target + ".html"' in ja
    assert "api.apply_settings(res.size, target)" in ja


def test_section_titles_and_catalog_messages_per_locale(tmp_path):
    vi = _html(tmp_path / "vi", "vi")
    en = _html(tmp_path / "en", "en")
    ja = _html(tmp_path / "ja", "ja")

    assert "Nghiên cứu" in vi and "Công nghệ" in vi
    assert "Research" in en and "Tech News" in en
    assert "論文" in ja and "テックニュース" in ja

    assert _messages(vi)["story_save"] == "Lưu"
    assert _messages(en)["story_save"] == "Save"
    assert _messages(ja)["story_save"] == "保存"
    assert _messages(ja)["overview_takeaway_marker"] == "要点:"


def test_chrome_has_no_cross_locale_sentinels(tmp_path):
    en = _html(tmp_path / "en", "en")
    ja = _html(tmp_path / "ja", "ja")

    assert "Nghiên cứu" not in en
    assert "Nghiên cứu" not in ja
    assert "Research" not in ja


def test_ai_summary_label_uses_css_custom_property(tmp_path):
    ja = _html(tmp_path / "ja", "ja")
    assert "--label-ai-summary:" in ja
    assert "AI要約" in ja
    assert 'content: var(--label-ai-summary, "AI SUMMARY")' in ja


def test_japanese_typography_and_print_rules(tmp_path):
    ja = _html(tmp_path / "ja", "ja")
    assert 'html[lang="ja"]' in ja
    assert "Yu Mincho" in ja
    assert "line-break: strict" in ja
    assert "overflow-wrap: break-word" in ja
    assert 'html[lang="ja"] body { line-height: 1.45; }' in ja
