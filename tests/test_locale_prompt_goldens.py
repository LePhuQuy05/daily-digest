"""Explicit vi/en/ja prompt goldens; prompt drift must be reviewed."""

from __future__ import annotations

from pathlib import Path

import pytest

from daily_digest.i18n import PROMPT_LANGUAGE, takeaway_marker
from daily_digest.ranking.llm import (
    MAX_WHY,
    MAX_WHY_JA,
    SUMMARIZE_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    mix_guidance,
    overview_char_budget,
)

FIXTURES = Path(__file__).parent / "fixtures" / "prompts"


def _editor(locale: str) -> str:
    return SYSTEM_PROMPT.format(
        topics="LLM, agents",
        top_n=12,
        mix_guidance=mix_guidance(12),
        reader_context="",
        always_rule="",
        language=PROMPT_LANGUAGE[locale],
        why_limit=MAX_WHY_JA if locale == "ja" else MAX_WHY,
    )


def _writer(locale: str) -> str:
    return SUMMARIZE_SYSTEM_PROMPT.format(
        topics="LLM, agents",
        summary_limit="180 Japanese characters" if locale == "ja" else "70 words",
        language=PROMPT_LANGUAGE[locale],
        reader_context="",
        overview_chars=overview_char_budget(12, locale),
        density_hint="",
        takeaway_marker=takeaway_marker(locale),
        japanese_guard=(
            "\nUse natural Japanese; keep standard technical names in Latin script. "
            if locale == "ja"
            else ""
        ),
    )


@pytest.mark.parametrize("locale", ["vi", "en", "ja"])
def test_editor_prompt_matches_explicit_golden(locale: str):
    expected = (FIXTURES / f"{locale}-editor.txt").read_text(encoding="utf-8")
    assert _editor(locale) == expected


@pytest.mark.parametrize("locale", ["vi", "en", "ja"])
def test_writer_prompt_matches_explicit_golden(locale: str):
    expected = (FIXTURES / f"{locale}-writer.txt").read_text(encoding="utf-8")
    assert _writer(locale) == expected


@pytest.mark.parametrize("locale", ["vi", "en", "ja"])
def test_goldens_do_not_mix_locale_markers(locale: str):
    writer = _writer(locale)
    assert f"Write the overview in {PROMPT_LANGUAGE[locale]}" in writer
    assert f"End with a point starting with '{takeaway_marker(locale)}'" in writer
    if locale != "vi":
        assert "Điểm cần nhớ" not in writer
    if locale != "ja":
        assert "要点:" not in writer
