"""Pipeline coverage: LLM citations and every fallback mode still link items."""

from __future__ import annotations

import json

import daily_digest.pipeline as pipeline
from daily_digest.pipeline import run_day
from helpers import FakeLlmClient, llm_ok_json, make_config, make_item


DATE = "2026-11-19"


def _items():
    return [
        make_item(
            id=f"arxiv:2611.{i:05d}",
            title=f"Paper {i}",
            url=f"https://arxiv.org/abs/{2611}.{i:05d}",
            source="arxiv",
            summary=f"summary {i}",
        )
        for i in range(3)
    ]


def _writer(overview: str = "Bài [[0]] và [[1]].\n\nĐiểm cần nhớ: ưu tiên đọc."):
    return FakeLlmClient(
        json.dumps(
            {
                "overview": overview,
                "items": [{"id": i, "summary": f"sum {i}"} for i in range(3)],
            }
        )
    )


def _run(tmp_path, monkeypatch, *, llm_client, summary_client, summarize=True):
    config = make_config(tmp_path)
    config.llm.summarize = summarize
    config.llm.section_briefs = False  # this module covers the legacy global rail
    monkeypatch.setattr(pipeline, "fetch_all", lambda client, cfg: (_items(), []))
    return run_day(
        config,
        DATE,
        llm_client=llm_client,
        summary_client=summary_client,
        notify_fn=lambda *a, **k: None,
    )


def _assert_all_items_linked(html: str):
    for item in _items():
        assert f'href="#story-{item.id}"' in html
    assert html.count('class="oref"') == len(_items())
    assert "[[" not in html


def test_llm_overview_markers_render_and_cover_rest(tmp_path, monkeypatch):
    # Writer cites only two items; the third must come from "Còn lại hôm nay".
    result = _run(
        tmp_path,
        monkeypatch,
        llm_client=FakeLlmClient(llm_ok_json(8)),
        summary_client=_writer(),
    )

    html = result.digest_path.read_text(encoding="utf-8")
    assert result.exit_code == 0
    assert "Còn lại hôm nay" in html
    _assert_all_items_linked(html)


def test_no_summary_client_uses_heuristic_coverage(tmp_path, monkeypatch):
    result = _run(
        tmp_path,
        monkeypatch,
        llm_client=FakeLlmClient(llm_ok_json(8)),
        summary_client=None,
    )
    _assert_all_items_linked(result.digest_path.read_text(encoding="utf-8"))


def test_writer_failure_uses_heuristic_coverage(tmp_path, monkeypatch):
    result = _run(
        tmp_path,
        monkeypatch,
        llm_client=FakeLlmClient(llm_ok_json(8)),
        summary_client=FakeLlmClient(["not json", "still not json"]),
    )
    _assert_all_items_linked(result.digest_path.read_text(encoding="utf-8"))


def test_summarize_disabled_uses_heuristic_coverage(tmp_path, monkeypatch):
    result = _run(
        tmp_path,
        monkeypatch,
        llm_client=FakeLlmClient(llm_ok_json(8)),
        summary_client=None,
        summarize=False,
    )
    _assert_all_items_linked(result.digest_path.read_text(encoding="utf-8"))


def test_heuristic_ranking_uses_heuristic_coverage(tmp_path, monkeypatch):
    result = _run(
        tmp_path,
        monkeypatch,
        llm_client=None,
        summary_client=None,
    )
    _assert_all_items_linked(result.digest_path.read_text(encoding="utf-8"))
