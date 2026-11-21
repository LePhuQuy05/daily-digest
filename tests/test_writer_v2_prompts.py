"""Writer v2 prompts: explicit locale goldens and style invariants."""

from __future__ import annotations

from pathlib import Path

import pytest

from daily_digest.i18n import takeaway_marker
from daily_digest.ranking.llm import overview_char_budget
from daily_digest.ranking.writer_prompts import (
    item_summary_limit,
    item_system_prompt,
    overview_system_prompt,
    overview_target_range,
)

FIXTURES = Path(__file__).parent / "fixtures" / "prompts"


def _item(locale: str) -> str:
    return item_system_prompt(
        locale,
        topics="LLM, agents",
        reader_context="",
        limit=item_summary_limit(70, locale),
    )


def _overview(locale: str) -> str:
    return overview_system_prompt(
        locale,
        topics="LLM, agents",
        reader_context="",
        target=overview_target_range(12, locale),
        hard_cap=overview_char_budget(12, locale),
        takeaway=takeaway_marker(locale),
        item_count=12,
    )


@pytest.mark.parametrize("locale", ["vi", "en", "ja"])
def test_writer_v2_item_prompt_golden(locale: str):
    expected = (FIXTURES / f"{locale}-items.txt").read_text(encoding="utf-8")
    assert _item(locale) == expected


@pytest.mark.parametrize("locale", ["vi", "en", "ja"])
def test_writer_v2_overview_prompt_golden(locale: str):
    expected = (FIXTURES / f"{locale}-overview.txt").read_text(encoding="utf-8")
    assert _overview(locale) == expected


def test_writer_v2_prompts_are_native_and_do_not_enumerate_every_item():
    assert "Never open with" in _item("en")
    assert "です・ます" in _item("ja")
    assert "biên tập viên" in _item("vi")
    assert "Every numbered item" not in _overview("en")
    assert "Cite only the 3-6" in _overview("en")
    assert "[[n]]" in _overview("en")
    assert "absolute item number" in _item("en")
