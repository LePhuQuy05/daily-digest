"""F4 profile context: loader caps/fallbacks, golden prompt byte-identity, wiring."""

import logging

import daily_digest.pipeline as pipeline
from daily_digest.config import Config, load_config
from daily_digest.pipeline import run_day
from daily_digest.profile import load_profile, profile_block
from daily_digest.ranking.llm import (
    SYSTEM_PROMPT,
    SUMMARIZE_SYSTEM_PROMPT,
    mix_guidance,
)
from helpers import FakeLlmClient, llm_ok_json, make_config, make_item

# Golden: the EXACT rendered prompts as of the F4 change, captured before the
# {reader_context}/{always_rule} slots were added. Empty inputs must reproduce
# these byte-for-byte forever.
def test_editor_prompt_has_locale_language_and_why_limit():
    rendered = SYSTEM_PROMPT.format(
        topics="LLM, agents",
        top_n=12,
        mix_guidance=mix_guidance(12),
        reader_context="",
        always_rule="",
        language="Vietnamese",
        why_limit=140,
    )
    assert 'Write each "why" in Vietnamese.' in rendered
    assert "under 140 characters" in rendered


def test_writer_prompt_has_locale_language_and_marker():
    rendered = SUMMARIZE_SYSTEM_PROMPT.format(
        topics="LLM, agents",
        summary_limit="70 words",
        language="Vietnamese",
        reader_context="",
        overview_chars=1600,
        density_hint="",
        takeaway_marker="Điểm cần nhớ:",
        japanese_guard="",
    )
    assert "End with a point starting with 'Điểm cần nhớ:'." in rendered
    assert "at most 70 words" in rendered
    assert "Write every per-item summary in Vietnamese." in rendered


def test_prompt_with_context_inserts_after_interests_line():
    block = "About the reader's current work, in their own words: building a RAG eval tool\n"
    rendered = SYSTEM_PROMPT.format(
        topics="LLM",
        top_n=12,
        mix_guidance=mix_guidance(12),
        reader_context=block,
        always_rule="",
        language="Vietnamese",
        why_limit=140,
    )
    assert rendered.index("Their interests: LLM.\n") < rendered.index(block)
    assert rendered.index(block) < rendered.index("From the numbered candidates")


# ------------------------------------------------------------------ profile loader


def test_load_profile_missing_file_returns_empty(tmp_path):
    config = make_config(tmp_path)
    config.llm.profile_file = str(tmp_path / "nope.md")
    assert load_profile(config) == ""


def test_load_profile_disabled_returns_empty(tmp_path):
    config = make_config(tmp_path)
    config.llm.profile_file = ""
    assert load_profile(config) == ""


def test_load_profile_reads_and_collapses_whitespace(tmp_path):
    config = make_config(tmp_path)
    profile = tmp_path / "profile.md"
    profile.write_text(
        "I am building   a\n\nfine-tuning   pipeline for Vietnamese.", encoding="utf-8"
    )
    config.llm.profile_file = str(profile)
    assert (
        load_profile(config) == "I am building a fine-tuning pipeline for Vietnamese."
    )


def test_load_profile_caps_on_word_boundary(tmp_path):
    config = make_config(tmp_path)
    config.llm.profile_max_chars = 40
    profile = tmp_path / "profile.md"
    profile.write_text(" ".join(f"word{i}" for i in range(100)), encoding="utf-8")
    config.llm.profile_file = str(profile)
    text = load_profile(config)
    assert len(text) <= 41  # 40 + ellipsis
    assert text.endswith("…")
    assert "word0 word1" in text  # cut at a word boundary, not mid-word


def test_load_profile_unreadable_warns_and_returns_empty(tmp_path, caplog):
    config = make_config(tmp_path)
    config.llm.profile_file = str(tmp_path)  # a directory: read_text raises OSError
    with caplog.at_level(logging.WARNING):
        text = load_profile(config)
    assert text == ""
    assert "unreadable" in caplog.text


def test_profile_block_empty_and_content():
    assert profile_block("") == ""
    block = profile_block("building agent evals")
    assert (
        block
        == "About the reader's current work, in their own words: building agent evals\n"
    )
    assert profile_block(
        "weird {braces} and }{ chars are fine"
    )  # concat only, no format()


def test_profile_with_braces_never_breaks_format():
    block = profile_block("uses {custom} templates")
    rendered = SYSTEM_PROMPT.format(
        topics="LLM",
        top_n=5,
        mix_guidance=mix_guidance(5),
        reader_context=block,
        always_rule="",
        language="Vietnamese",
        why_limit=140,
    )
    assert "{custom}" in rendered  # substituted value is not re-formatted


# ------------------------------------------------------------------ pipeline wiring


def _items():
    return [
        make_item(
            id=f"hn:{i}",
            title=f"LLM paper {i}",
            url=f"https://example.com/{i}",
            source="hn",
            points=100 + i,
        )
        for i in range(5)
    ]


def test_run_day_injects_profile_into_both_prompts(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    profile = tmp_path / "profile.md"
    profile.write_text(
        "I am building a Vietnamese RAG evaluation platform.", encoding="utf-8"
    )
    config.llm.profile_file = str(profile)
    monkeypatch.setattr(pipeline, "fetch_all", lambda client, cfg: (_items(), []))

    editor = FakeLlmClient(llm_ok_json(8))
    writer = FakeLlmClient('{"overview": "ok", "items": []}')
    result = run_day(
        config,
        "2026-11-18",
        llm_client=editor,
        summary_client=writer,
        notify_fn=lambda *a, **k: None,
    )
    assert result.exit_code == 0
    editor_system = editor.chat.calls[0][0]["content"]
    writer_system = writer.chat.calls[0][0]["content"]
    assert "Vietnamese RAG evaluation platform" in editor_system
    assert "Vietnamese RAG evaluation platform" in writer_system


def test_run_day_without_profile_prompts_stay_golden(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    config.llm.profile_file = ""
    monkeypatch.setattr(pipeline, "fetch_all", lambda client, cfg: (_items(), []))

    editor = FakeLlmClient(llm_ok_json(8))
    writer = FakeLlmClient('{"overview": "ok", "items": []}')
    result = run_day(
        config,
        "2026-11-18",
        llm_client=editor,
        summary_client=writer,
        notify_fn=lambda *a, **k: None,
    )
    assert result.exit_code == 0
    topics = ", ".join(config.interests.topics)
    editor_system = editor.chat.calls[0][0]["content"]
    writer_system = writer.chat.calls[0][0]["content"]
    assert 'Write each "why" in Vietnamese.' in editor_system
    assert "at most 70 words" in writer_system
    assert "Write the overview in Vietnamese" in writer_system
    assert "Write every per-item summary in Vietnamese" in writer_system
    assert "About the reader's current work" not in editor_system
    assert "About the reader's current work" not in writer_system


def test_config_profile_defaults_and_yaml():
    config = Config()
    assert config.llm.profile_file == "profile.md"
    assert config.llm.profile_max_chars == 600
