"""Writer v2: split stages, absolute indices, independent fallbacks."""

from __future__ import annotations

import dataclasses
import json
import time

import daily_digest.pipeline as pipeline
from daily_digest.edition import load_edition
from daily_digest.i18n import t
from daily_digest.model import RankedItem
from daily_digest.pipeline import run_day
from daily_digest.ranking.llm import LlmError, summarize_with_llm, writer_deadline
from helpers import FakeChat, FakeLlmClient, llm_ok_json, make_config, make_item


def _ranked(count: int = 13) -> list[RankedItem]:
    return [
        RankedItem(
            item=make_item(
                id=f"arxiv:{i:05d}",
                title=f"Paper {i}",
                url=f"https://arxiv.org/abs/{i}",
                source="arxiv",
                summary=f"Source abstract {i} with method M{i} and result {i}0%.",
            ),
            why=f"why {i}",
            section="papers",
        )
        for i in range(count)
    ]


def _items_payload(start: int, count: int) -> str:
    return json.dumps(
        {
            "items": [
                {"id": start + offset, "summary": f"Summary {start + offset}"}
                for offset in range(count)
            ]
        }
    )


def _overview_payload() -> str:
    return json.dumps(
        {
            "overview": (
                "Two themes: inference and evaluation [[0]].\n\n"
                "Key takeaway: test the concrete method."
            )
        }
    )


class ScriptedChat:
    """Return or raise the next scripted step; records each call."""

    def __init__(self, steps):
        self.steps = list(steps)
        self.calls: list[list[dict]] = []

    def __call__(self, messages: list[dict]) -> str:
        self.calls.append(messages)
        step = self.steps.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


def test_writer_v2_splits_batches_with_absolute_indices(tmp_path):
    config = make_config(tmp_path)
    config.llm.writer_v2 = True
    chat = FakeChat(
        [
            _items_payload(0, 12),
            _items_payload(12, 1),
            _overview_payload(),
        ]
    )

    ranked, overview = summarize_with_llm(_ranked(13), chat, config, locale="en")

    assert len(chat.calls) == 3
    assert [item.llm_summary for item in ranked] == [f"Summary {i}" for i in range(13)]
    assert "Two themes" in overview
    second_user = chat.calls[1][1]["content"]
    assert "[12]" in second_user
    assert "[0]" not in second_user


def test_writer_v2_30_items_keep_absolute_index_identity(tmp_path):
    config = make_config(tmp_path)
    config.llm.writer_v2 = True
    chat = FakeChat(
        [
            _items_payload(0, 12),
            _items_payload(12, 12),
            _items_payload(24, 6),
            _overview_payload(),
        ]
    )

    ranked, overview = summarize_with_llm(_ranked(30), chat, config, locale="en")

    assert len(chat.calls) == 4
    assert [item.llm_summary for item in ranked] == [f"Summary {i}" for i in range(30)]
    assert [item.item.id for item in ranked] == [f"arxiv:{i:05d}" for i in range(30)]
    first = chat.calls[0][1]["content"]
    second = chat.calls[1][1]["content"]
    third = chat.calls[2][1]["content"]
    assert "[0]" in first and "[11]" in first and "[12]" not in first
    assert "[12]" in second and "[23]" in second
    assert "[0]" not in second and "[24]" not in second
    assert "[24]" in third and "[29]" in third and "[0]" not in third
    assert "Two themes" in overview


def test_writer_v2_ignores_index_outside_current_batch(tmp_path):
    config = make_config(tmp_path)
    config.llm.writer_v2 = True
    bleed = json.dumps(
        {
            "items": [
                {"id": 0, "summary": "WRONG cross-batch summary"},
                {"id": 12, "summary": "Summary 12"},
            ]
        }
    )
    chat = FakeChat([_items_payload(0, 12), bleed, _overview_payload()])

    ranked, _ = summarize_with_llm(_ranked(13), chat, config, locale="en")

    assert ranked[0].llm_summary == "Summary 0"
    assert ranked[12].llm_summary == "Summary 12"


def test_writer_v2_item_batch_failure_keeps_other_batches(tmp_path):
    config = make_config(tmp_path)
    config.llm.writer_v2 = True
    chat = FakeChat(
        [
            "not json",
            "still not json",
            _items_payload(12, 1),
            '{"items": []}',
            _overview_payload(),
        ]
    )

    ranked, overview = summarize_with_llm(_ranked(13), chat, config, locale="en")

    assert len(chat.calls) == 5  # 2 failed batch calls + batch 2 + repair + overview
    assert all(not item.llm_summary for item in ranked[:12])
    assert ranked[12].llm_summary == "Summary 12"
    assert overview


def test_writer_v2_ja_truncation_stops_at_sentence_boundary(tmp_path):
    config = make_config(tmp_path)
    config.llm.writer_v2 = True
    long_text = "これは具体的な結果を示す文です。" * 20
    payload = json.dumps({"items": [{"id": 0, "summary": long_text}]})
    chat = FakeChat([payload, _overview_payload()])

    ranked, _ = summarize_with_llm(_ranked(1), chat, config, locale="ja")

    summary = ranked[0].llm_summary
    assert len(summary) <= 240
    assert summary.endswith("。")
    assert len(summary) < len(long_text)


def test_writer_v2_transport_failure_isolated_to_batch(tmp_path):
    config = make_config(tmp_path)
    config.llm.writer_v2 = True
    chat = ScriptedChat(
        [
            LlmError("endpoint down"),
            _items_payload(12, 1),
            '{"items": []}',
            _overview_payload(),
        ]
    )

    ranked, overview = summarize_with_llm(_ranked(13), chat, config, locale="en")

    assert len(chat.calls) == 4  # failed batch + batch 2 + repair + overview
    assert all(not item.llm_summary for item in ranked[:12])
    assert ranked[12].llm_summary == "Summary 12"
    assert "Two themes" in overview


def test_writer_v2_overview_transport_failure_keeps_summaries(tmp_path):
    config = make_config(tmp_path)
    config.llm.writer_v2 = True
    chat = ScriptedChat(
        [_items_payload(0, 12), _items_payload(12, 1), LlmError("endpoint down")]
    )

    ranked, overview = summarize_with_llm(_ranked(13), chat, config, locale="en")

    assert len(chat.calls) == 3
    assert all(item.llm_summary for item in ranked)
    assert overview == ""


def test_writer_v2_overview_failure_keeps_summaries(tmp_path):
    config = make_config(tmp_path)
    config.llm.writer_v2 = True
    chat = FakeChat(
        [_items_payload(0, 12), _items_payload(12, 1), "bad overview", "still bad"]
    )

    ranked, overview = summarize_with_llm(_ranked(13), chat, config, locale="en")

    assert len(chat.calls) == 4
    assert all(item.llm_summary for item in ranked)
    assert overview == ""


def test_writer_v2_deadline_stops_before_calls(tmp_path):
    config = make_config(tmp_path)
    config.llm.writer_v2 = True
    chat = FakeChat([_items_payload(0, 1), _overview_payload()])

    with writer_deadline(time.monotonic() - 1):
        ranked, overview = summarize_with_llm(_ranked(1), chat, config, locale="en")

    assert chat.calls == []
    assert ranked[0].llm_summary == ""
    assert overview == ""


def test_writer_v2_default_off_keeps_one_call(tmp_path):
    config = make_config(tmp_path)
    chat = FakeChat(
        json.dumps(
            {
                "overview": "One call overview.",
                "items": [{"id": 0, "summary": "one call summary"}],
            }
        )
    )

    ranked, overview = summarize_with_llm(_ranked(1), chat, config, locale="en")

    assert len(chat.calls) == 1
    assert ranked[0].llm_summary == "one call summary"
    assert overview == "One call overview."


def test_run_day_writer_v2_partial_summaries_degraded(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    config.llm.writer_v2 = True
    items = [
        make_item(
            id=f"arxiv:{i}",
            title=f"Paper {i}",
            url=f"https://arxiv.org/abs/{i}",
            source="arxiv",
            summary=f"Abstract {i}",
        )
        for i in range(2)
    ]
    monkeypatch.setattr(pipeline, "fetch_all", lambda client, cfg: (items, []))

    def fake_summarize(ranked, chat, config, reader_context="", locale="vi"):
        ranked = list(ranked)
        ranked[0] = dataclasses.replace(ranked[0], llm_summary="only one")
        ranked[1] = dataclasses.replace(ranked[1], llm_summary="")
        return ranked, "Overview [[0]]"

    monkeypatch.setattr(pipeline, "summarize_with_llm", fake_summarize)
    result = run_day(
        config,
        "2026-11-18",
        llm_client=FakeLlmClient(llm_ok_json(8)),
        summary_client=FakeLlmClient("unused"),
        notify_fn=lambda *a, **k: None,
    )

    assert result.degraded is True
    assert result.exit_code == 1
    saved = load_edition(config.output_dir, "2026-11-18")
    assert saved is not None
    assert saved.notice_key == "writer_partial"
    assert saved.notice_text == t("vi", "writer_partial")
    html = result.digest_path.read_text(encoding="utf-8")
    assert t("vi", "writer_partial") in html
