"""Locale catalogs, fallback, dates, and CJK text helpers."""

from __future__ import annotations

import string
from datetime import datetime

from daily_digest.i18n import (
    SUPPORTED_LOCALES,
    format_date_long,
    format_short_date,
    locale_strings,
    normalize_locale,
    normalize_markers,
    resolve_locale,
    section_title,
    split_sentences,
    t,
    truncate_overview,
)
from helpers import make_config


def test_normalize_locale_accepts_common_forms():
    assert normalize_locale("vi") == "vi"
    assert normalize_locale("ja-JP") == "ja"
    assert normalize_locale("JA") == "ja"
    assert normalize_locale("ja_JP") == "ja"
    assert normalize_locale("en-US") == "en"
    assert normalize_locale("xx") is None
    assert normalize_locale(None) is None


def test_catalog_key_and_placeholder_parity():
    catalogs = {locale: locale_strings(locale) for locale in SUPPORTED_LOCALES}
    keys = set(catalogs["vi"])
    assert set(catalogs["en"]) == keys
    assert set(catalogs["ja"]) == keys
    for key in keys:
        placeholders = {
            locale: {
                field
                for _, field, _, _ in string.Formatter().parse(catalogs[locale][key])
                if field
            }
            for locale in SUPPORTED_LOCALES
        }
        assert placeholders["vi"] == placeholders["en"] == placeholders["ja"], key


def test_fallback_and_formatting():
    assert t("vi", "story_points", n=4) == "4 điểm"
    assert t("en", "story_points", n=4) == "4 points"
    assert t("ja", "story_points", n=4) == "4ポイント"
    assert t("ja", "does_not_exist") == "does_not_exist"


def test_resolve_locale_precedence(tmp_path):
    config = make_config(tmp_path)
    config.llm.overview_language = "en"
    assert resolve_locale(config, {}) == "en"
    assert resolve_locale(config, {"language": "ja"}) == "ja"
    assert resolve_locale(config, {"language": "ja"}, "vi") == "vi"

    config.llm.overview_language = "xx"
    assert resolve_locale(config, {}) == "vi"
    assert resolve_locale(config, {"language": "xx"}) == "vi"


def test_dates_are_locale_specific():
    assert format_date_long("2026-11-21", "vi") == "THỨ BẢY, 21.11.2026"
    assert format_date_long("2026-11-21", "en") == "SATURDAY, 21.11.2026"
    assert format_date_long("2026-11-21", "ja") == "2026年11月21日（土）"
    assert format_date_long("invalid", "ja") == "invalid"
    assert format_short_date(None, "ja") == ""
    assert format_short_date(datetime(2026, 11, 21), "ja") == "2026年11月21日"


def test_section_titles_and_messages():
    assert section_title("papers", "vi") == "Nghiên cứu"
    assert section_title("papers", "en") == "Research"
    assert section_title("papers", "ja") == "論文"
    assert "settings_title" in locale_strings("ja")


def test_sentence_splitting_blank_lines_and_ja_punctuation():
    assert split_sentences("Một câu. Hai câu.", "vi") == ["Một câu.", "Hai câu."]
    assert split_sentences("Một đoạn.\n\nĐoạn khác.", "vi") == [
        "Một đoạn.",
        "Đoạn khác.",
    ]
    assert split_sentences("一つです。二つです！三つ？", "ja") == [
        "一つです。",
        "二つです！",
        "三つ？",
    ]
    assert split_sentences("「一つです。」二つです。", "ja") == [
        "「一つです。」",
        "二つです。",
    ]
    # ASCII dots inside versions/URLs must not split Japanese text.
    assert split_sentences("v1.2.3 と 3.14 は安全です。次です。", "ja") == [
        "v1.2.3 と 3.14 は安全です。",
        "次です。",
    ]
    assert split_sentences("one line\nwrapped line", "en") == ["one line wrapped line"]


def test_fullwidth_markers_and_truncation():
    assert normalize_markers("［［0］］") == "[[0]]"
    text = "あ" * 100 + "[[0]]"
    cut = truncate_overview(text, 50, "ja")
    assert len(cut) <= 51
    assert "[[" not in cut and "]]" not in cut
    assert "。" in truncate_overview("あ" * 40 + "。次", 42, "ja")

    for marker in ("[[", "[[0", "[[0]"):
        cut = truncate_overview("あ" * 60 + marker, 20, "ja")
        assert "[[" not in cut
