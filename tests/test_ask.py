"""F2 ask-this-item: message assembly, never-raises semantics, the popup's
single-shot LLM budget, and the read-only state reader."""

import json

import pytest

import daily_digest.ask as ask_mod
from daily_digest.ask import (
    ASK_MAX_RETRIES,
    ASK_SYSTEM_PROMPT,
    ASK_TIMEOUT_SECONDS,
    OFFLINE_MESSAGE,
    answer_question,
    build_ask_messages,
    build_popup_llm,
)
from daily_digest.popup_bridge import DigestBridge
from helpers import FakeChat, make_config, make_item

SNAPSHOT = {
    "title": "Reward hacking pressure states in LLM agents",
    "url": "https://arxiv.org/abs/2611.14996",
    "source": "arxiv",
    "points": None,
    "citations": 3,
    "summary": "We study internal pressure states that precede reward hacking.",
    "llm_summary": "The paper finds a task-badness direction that rises before hacks.",
    "why": "core safety topic",
    "section": "papers",
}


# ------------------------------------------------------------------ messages


def test_build_ask_messages_contains_all_grounding():
    messages = build_ask_messages(
        SNAPSHOT, "Does it beat prior work?", profile="building evals"
    )
    system, user = messages[0]["content"], messages[1]["content"]
    assert system.startswith("You are the assistant inside a daily tech digest")
    assert "building evals" in system  # profile context included when given
    assert "TITLE: Reward hacking pressure states" in user
    assert "SOURCE: arxiv" in user
    assert "DESCRIPTION: We study internal pressure states" in user
    assert "DIGEST SUMMARY: The paper finds" in user
    assert "QUESTION: Does it beat prior work?" in user


def test_build_ask_messages_without_profile_has_no_profile_line():
    messages = build_ask_messages(SNAPSHOT, "q")
    assert "Context about the reader" not in messages[0]["content"]


def test_build_ask_messages_truncates_long_fields():
    snapshot = dict(SNAPSHOT, summary="x " * 2000, llm_summary="y " * 1000)
    user = build_ask_messages(snapshot, "q")[1]["content"]
    description = user.split("DESCRIPTION: ", 1)[1].split("\n", 1)[0]
    summary = user.split("DIGEST SUMMARY: ", 1)[1].split("\n", 1)[0]
    assert len(description) <= 1300  # capped ~1200
    assert len(summary) <= 700  # capped ~600


def test_ask_system_prompt_profile_with_braces_is_safe():
    messages = build_ask_messages(SNAPSHOT, "q", profile="uses {custom} {templates}")
    assert "{custom}" in messages[0]["content"]  # substituted value never re-formatted


# ------------------------------------------------------------------ never raises


def test_answer_question_returns_chat_answer():
    chat = FakeChat("The paper introduces a direction, not a benchmark win.")
    assert (
        answer_question(SNAPSHOT, "q", chat)
        == "The paper introduces a direction, not a benchmark win."
    )
    assert len(chat.calls) == 1


def test_answer_question_offline_without_key():
    assert answer_question(SNAPSHOT, "q", None) == OFFLINE_MESSAGE
    assert "OPENCODE_API_KEY" in OFFLINE_MESSAGE


def test_answer_question_raising_chat_returns_polite_message():
    class Exploding:
        def __call__(self, messages):
            raise RuntimeError("boom")

    answer = answer_question(SNAPSHOT, "q", Exploding())
    assert "Chưa hỏi được" in answer


def test_answer_question_empty_answer_is_replaced():
    chat = FakeChat("   ")
    assert "câu trả lời rỗng" in answer_question(SNAPSHOT, "q", chat)


# ------------------------------------------------------------------ popup LLM budget


def test_build_popup_llm_no_key_returns_none(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
    assert build_popup_llm(config) is None


def test_build_popup_llm_single_shot_budget_and_readonly_session(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    monkeypatch.setenv("OPENCODE_API_KEY", "test-key")
    config.state_path.write_text(
        json.dumps({"llm_session": "ses_run_123"}), encoding="utf-8"
    )

    client = build_popup_llm(config)
    assert client is not None
    assert client.session_id == "ses_run_123"  # reused, not replaced
    assert client.config.llm.timeout_seconds == ASK_TIMEOUT_SECONDS  # 45, not 90
    assert client.config.llm.max_retries == ASK_MAX_RETRIES  # 0, not 2
    # and the state file was NOT rewritten
    assert json.loads(config.state_path.read_text(encoding="utf-8")) == {
        "llm_session": "ses_run_123"
    }


def test_build_popup_llm_ephemeral_session_when_state_missing(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    monkeypatch.setenv("OPENCODE_API_KEY", "test-key")
    client = build_popup_llm(config)
    assert client.session_id.startswith("ses_popup_")


def test_build_popup_llm_with_corrupt_state_creates_no_corrupt_file(
    tmp_path, monkeypatch
):
    """THE popup-must-not-write-state.json invariant: a corrupt state.json must
    NOT be renamed/repaired by the popup process (util.load_json would!)."""
    config = make_config(tmp_path)
    monkeypatch.setenv("OPENCODE_API_KEY", "test-key")
    config.state_path.parent.mkdir(parents=True, exist_ok=True)
    config.state_path.write_text("{corrupt beyond repair", encoding="utf-8")
    before = config.state_path.read_text(encoding="utf-8")

    client = build_popup_llm(config)
    assert client is not None
    assert client.session_id.startswith("ses_popup_")  # ephemeral fallback
    assert config.state_path.read_text(encoding="utf-8") == before  # untouched
    assert not (tmp_path / "state.json.corrupt").exists()  # never renamed
    assert not (tmp_path / "state.json.tmp").exists()


# ------------------------------------------------------------------ bridge.ask


def _bridge(config, chat_factory):
    return DigestBridge(
        config,
        {"date": "2026-11-19", "items": {"hn:1": SNAPSHOT}, "pinned": []},
        chat_factory=chat_factory,
    )


def test_bridge_ask_answers_via_factory(tmp_path):
    config = make_config(tmp_path)
    calls = []

    def factory(cfg):
        calls.append(cfg)
        return FakeChat("Grounded answer about the paper.")

    bridge = _bridge(config, factory)
    answer = bridge.ask("hn:1", "What is the key finding?")
    assert answer == "Grounded answer about the paper."
    assert len(calls) == 1  # built lazily, exactly once


def test_bridge_ask_reuses_client_across_questions(tmp_path):
    config = make_config(tmp_path)
    builds = []

    def factory(cfg):
        builds.append(1)
        return FakeChat("answer two")

    bridge = _bridge(config, factory)
    bridge.ask("hn:1", "first")
    bridge.ask("hn:1", "second")
    assert len(builds) == 1  # lazy singleton


def test_bridge_ask_offline_and_unknown_uid_and_empty_question(tmp_path):
    config = make_config(tmp_path)
    bridge = _bridge(config, lambda cfg: None)
    assert bridge.ask("hn:1", "q") == OFFLINE_MESSAGE
    assert "Không tìm thấy" in bridge.ask("hn:999", "q")
    assert "chưa nhập câu hỏi" in bridge.ask("hn:1", "   ")


def test_bridge_ask_never_raises_even_when_factory_explodes(tmp_path):
    config = make_config(tmp_path)

    def factory(cfg):
        raise RuntimeError("factory boom")

    bridge = _bridge(config, factory)
    answer = bridge.ask("hn:1", "q")
    assert "Chưa hỏi được" in answer  # swallowed into a polite string
