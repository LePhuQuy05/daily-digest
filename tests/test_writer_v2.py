"""Writer v2: split stages, absolute indices, independent fallbacks."""

from __future__ import annotations

import dataclasses
import json
import time

import daily_digest.pipeline as pipeline
from daily_digest.model import RankedItem
from daily_digest.pipeline import run_day
from daily_digest.ranking.llm import summarize_with_llm
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


def test_writer_v2_item_batch_failure_keeps_other_batches(tmp_path):
    config = make_config(tmp_path)
    config.llm.writer_v2 = True
    chat = FakeChat(
        [
            "not json",
            "still not json",
            _items_payload(12, 1),
            _overview_payload(),
        ]
    )

    ranked, overview = summarize_with_llm(_ranked(13), chat, config, locale="en")

    assert len(chat.calls) == 4
    assert all(not item.llm_summary for item in ranked[:12])
    assert ranked[12].llm_summary == "Summary 12"
    assert overview


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

    ranked, overview = summarize_with_llm(
        _ranked(1),
        chat,
        config,
        locale="en",
        deadline=time.monotonic() - 1,
    )

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

    def fake_summarize(
        ranked, chat, config, reader_context="", locale="vi", deadline=None
    ):
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
