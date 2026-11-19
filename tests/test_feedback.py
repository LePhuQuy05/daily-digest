"""F1 feedback: atomic appends, tolerant reads, two-channel aggregation,
bounded context, item-clamped nudges, pinned lifecycle, bridge, pipeline."""

import json
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import daily_digest.pipeline as pipeline
from daily_digest.config import Config
from daily_digest.feedback import (
    FeedbackAggregate,
    TOPIC_ADJUST_CLAMP,
    aggregate,
    append_feedback,
    pinned_items,
    read_feedback,
    reader_context_block,
    topic_adjustments,
)
from daily_digest.popup_bridge import DigestBridge
from helpers import FakeLlmClient, llm_ok_json, make_config, make_item


def _snap(title="A paper about LLM agents", **extra):
    base = {
        "title": title,
        "url": "https://arxiv.org/abs/2611.1",
        "source": "arxiv",
        "points": None,
        "citations": None,
        "summary": "we study agents and LLM reasoning",
        "llm_summary": "",
        "why": "matches interests",
        "section": "papers",
    }
    base.update(extra)
    return base


# ------------------------------------------------------------------ append + read


def test_append_and_read_roundtrip(tmp_path):
    path = tmp_path / "feedback.jsonl"
    append_feedback(path, "hn:1", "like", "2026-11-19", _snap("Liked paper"))
    append_feedback(path, "hn:2", "save", "2026-11-19", _snap("Saved paper"))
    signals = read_feedback(path)
    assert [(s.uid, s.action) for s in signals] == [("hn:1", "like"), ("hn:2", "save")]
    assert signals[0].snapshot["title"] == "Liked paper"
    assert signals[0].ts  # ISO timestamp written


def test_append_truncates_snapshots(tmp_path):
    path = tmp_path / "feedback.jsonl"
    huge = "word " * 400  # ~2000 chars
    append_feedback(path, "hn:1", "like", "2026-11-19", _snap(summary=huge))
    line = path.read_text(encoding="utf-8").splitlines()[0]
    assert len(line) < 4000  # comfortably below any OS append granularity (8KB)
    record = json.loads(line)
    assert len(record["snapshot"]["summary"]) <= 1005  # capped at ~1000
    assert record["v"] == 1 and record["date"] == "2026-11-19"


def test_append_rejects_unknown_action(tmp_path):
    import pytest

    with pytest.raises(ValueError):
        append_feedback(tmp_path / "f.jsonl", "hn:1", "explode", "2026-11-19", {})


def test_read_tolerates_corrupt_partial_and_garbage(tmp_path):
    path = tmp_path / "feedback.jsonl"
    path.write_text(
        json.dumps(
            {
                "v": 1,
                "ts": "2026-11-19T09:00:00",
                "date": "2026-11-19",
                "uid": "hn:1",
                "action": "like",
                "snapshot": _snap(),
            }
        )
        + "\n"
        + "{torn line without newline"
        + "\nnot json at all\n"
        + "\n"
        + json.dumps(
            {
                "v": 1,
                "ts": "2026-11-19T09:01:00",
                "date": "2026-11-19",
                "uid": "hn:2",
                "action": "dislike",
                "snapshot": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    signals = read_feedback(path)
    assert [(s.uid, s.action) for s in signals] == [
        ("hn:1", "like"),
        ("hn:2", "dislike"),
    ]


def test_read_missing_file_is_empty(tmp_path):
    assert read_feedback(tmp_path / "nope.jsonl") == []


def test_concurrent_threads_append_all_lines_intact(tmp_path):
    """In-process version of the day-0 subprocess probe: N threads hammering
    append_feedback — every resulting line must parse."""
    path = tmp_path / "feedback.jsonl"

    def worker(tag):
        for i in range(60):
            append_feedback(
                path, f"hn:{tag}{i}", "like", "2026-11-19", _snap(f"paper {tag}{i}")
            )

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    signals = read_feedback(path)
    assert len(signals) == 240  # nothing lost, nothing torn
    assert len({s.uid for s in signals}) == 240


# ------------------------------------------------------------------ aggregation


def _signals_from(actions, day="2026-11-19"):
    """Build signals from [(uid, action, hours_ago)] with snapshots per uid."""
    snapshots = {}
    signals = []
    for uid, action, hours_ago in actions:
        if uid not in snapshots:
            snapshots[uid] = _snap(f"paper {uid}")
        ts = (
            datetime.fromisoformat("2026-11-19T12:00:00") - timedelta(hours=hours_ago)
        ).isoformat()
        signals.append(_signal(ts=ts, uid=uid, action=action, snapshot=snapshots[uid]))
    return signals


def _signal(ts, uid, action, snapshot):
    from daily_digest.feedback import FeedbackSignal

    return FeedbackSignal(
        ts=ts, date="2026-11-19", uid=uid, action=action, snapshot=snapshot
    )


def test_like_then_dislike_counts_once_as_dislike():
    signals = _signals_from([("hn:1", "like", 48), ("hn:1", "dislike", 24)])
    agg = aggregate(signals, "2026-11-19")
    assert agg.ratings == {"hn:1": "dislike"}
    assert agg.dislikes and not agg.likes  # the like is forgotten, not double-counted


def test_unlike_clears_rating():
    signals = _signals_from([("hn:1", "like", 48), ("hn:1", "unlike", 24)])
    agg = aggregate(signals, "2026-11-19")
    assert agg.ratings == {} and not agg.likes and not agg.dislikes


def test_ratings_older_than_window_are_ignored():
    old = _signals_from([("hn:1", "like", 20 * 24)])  # 20 days ago
    fresh = _signals_from([("hn:2", "dislike", 2)])
    agg = aggregate(old + fresh, "2026-11-19", window_days=14)
    assert agg.likes == [] and len(agg.dislikes) == 1


def test_saves_persist_beyond_window_until_unsave():
    old_save = _signals_from([("hn:1", "save", 30 * 24)])  # a month old
    agg = aggregate(old_save, "2026-11-19", window_days=14)
    assert "hn:1" in agg.saved  # pins are NOT window-pruned
    unsave = _signals_from([("hn:1", "save", 30 * 24), ("hn:1", "unsave", 1)])
    assert aggregate(unsave, "2026-11-19", window_days=14).saved == {}


def test_saved_snapshot_carries_uid():
    signals = _signals_from([("hn:9", "save", 1)])
    agg = aggregate(signals, "2026-11-19")
    assert agg.saved["hn:9"]["uid"] == "hn:9"


# ------------------------------------------------------------------ context + nudge


def test_reader_context_block_bounded_and_concatenated():
    agg = FeedbackAggregate(
        likes=[{"title": "like " + "x" * 200, "uid": "hn:1"}],
        dislikes=[{"title": "dislike " + "y" * 200, "uid": "hn:2"}],
        saved={"hn:3": {"title": "pinned {braces} title", "uid": "hn:3"}},
    )
    block = reader_context_block(agg, "my profile text", max_titles=10)
    assert "Recently LIKED" in block and "Recently DISLIKED" in block
    assert "Pinned by the reader" in block
    assert "my profile text" in block
    assert "{braces}" in block  # concatenation, no format() on titles
    assert block.endswith("\n")
    for line in block.splitlines():
        if line.startswith("- Recently"):
            assert len(line) < 200  # 80-char cap per title keeps lines small


def test_reader_context_block_empty_when_nothing():
    assert reader_context_block(FeedbackAggregate(), "", 10) == ""
    assert reader_context_block(FeedbackAggregate(), "profile only", 10).startswith(
        "Reader's recent signals"
    )


def test_topic_adjustments_clamped_per_topic():
    many_likes = FeedbackAggregate(
        likes=[
            {"title": f"LLM paper {i}", "summary": "agents", "uid": f"hn:{i}"}
            for i in range(20)
        ]
    )
    adj = topic_adjustments(many_likes, ["LLM"])
    assert adj["LLM"] == TOPIC_ADJUST_CLAMP  # 20 × 0.25 clamped at +1.0


# ------------------------------------------------------------------ pinned lifecycle


def test_pinned_items_cap_and_overflow():
    agg = FeedbackAggregate(
        saved={f"hn:{i}": {"uid": f"hn:{i}", "title": f"paper {i}"} for i in range(8)}
    )
    pinned = pinned_items(agg, cap=5)
    assert len(pinned) == 5
    overflow = len(agg.saved) - len(pinned)
    assert overflow == 3


# ------------------------------------------------------------------ bridge


def test_bridge_feedback_appends_with_snapshot(tmp_path):
    config = make_config(tmp_path)
    digest_data = {
        "date": "2026-11-19",
        "items": {"hn:1": _snap("Bridge paper")},
        "pinned": [],
    }
    bridge = DigestBridge(config, digest_data)
    result = bridge.feedback("hn:1", "like")
    assert result["ok"] is True
    signals = read_feedback(config.feedback_path)
    assert signals[0].uid == "hn:1" and signals[0].action == "like"
    assert signals[0].snapshot["title"] == "Bridge paper"
    assert signals[0].date == "2026-11-19"


def test_bridge_feedback_unknown_uid_and_action_and_pinned(tmp_path):
    config = make_config(tmp_path)
    digest_data = {
        "date": "2026-11-19",
        "items": {"hn:1": _snap()},
        "pinned": [
            {
                "uid": "hn:9",
                "title": "pinned old",
                "url": "https://x.io",
                "source": "arxiv",
            }
        ],
    }
    bridge = DigestBridge(config, digest_data)
    assert bridge.feedback("hn:999", "like")["ok"] is False  # unknown item
    assert bridge.feedback("hn:1", "explode")["ok"] is False  # unknown action
    assert (
        bridge.feedback("hn:9", "unsave")["ok"] is True
    )  # pinned items are actionable


def test_bridge_feedback_never_raises(tmp_path):
    config = make_config(tmp_path)
    digest_data = {"date": "2026-11-19", "items": {"hn:1": _snap()}, "pinned": []}
    bridge = DigestBridge(config, digest_data)
    config.feedback_path = tmp_path  # a directory -> append raises inside
    result = bridge.feedback("hn:1", "like")
    assert result["ok"] is False and "error" in result  # swallowed, no exception


# ------------------------------------------------------------------ pipeline


def _run(config, tmp_path, monkeypatch, editor=None):
    items = [
        make_item(
            id=f"hn:{i}",
            title=f"LLM paper {i}",
            url=f"https://example.com/{i}",
            source="hn",
            points=100 + i,
            summary=f"abstract {i}",
        )
        for i in range(5)
    ]
    monkeypatch.setattr(pipeline, "fetch_all", lambda client, cfg: (items, []))
    editor = editor or FakeLlmClient(llm_ok_json(8))
    return pipeline.run_day(
        config,
        "2026-11-19",
        llm_client=editor,
        summary_client=FakeLlmClient('{"overview": "ok", "items": []}'),
        notify_fn=lambda *a, **k: None,
    ), editor


def test_run_day_consumes_feedback_into_prompts_and_pin_section(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    append_feedback(
        config.feedback_path, "hn:0", "like", "2026-11-18", _snap("liked LLM paper 0")
    )
    append_feedback(
        config.feedback_path,
        "hn:77",
        "save",
        "2026-11-18",
        _snap("pinned for later reading"),
    )

    result, editor = _run(config, tmp_path, monkeypatch)
    assert result.exit_code == 0
    editor_system = editor.chat.calls[0][0]["content"]
    assert "Recently LIKED" in editor_system
    assert "liked LLM paper 0" in editor_system
    assert "Pinned by the reader" in editor_system
    html = result.digest_path.read_text(encoding="utf-8")
    assert "Nhìn lại" in html
    assert "pinned for later reading" in html
    blob = json.loads(html.split('id="digest-data">', 1)[1].split("</script>", 1)[0])
    assert any(entry["uid"] == "hn:77" for entry in blob["pinned"])


def test_run_day_pinned_in_today_ranked_shows_only_once(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    # hn:0 IS in today's fetch (see _run items) — pinned display drops it
    append_feedback(
        config.feedback_path, "hn:0", "save", "2026-11-18", _snap("today paper saved")
    )
    result, _ = _run(config, tmp_path, monkeypatch)
    html = result.digest_path.read_text(encoding="utf-8")
    assert (
        html.count("today paper saved") == 0
    )  # saved snapshot title differs; uid-based dedupe
    # the item appears in its normal section instead (title from fetch)


def test_run_day_unsave_clears_pin(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    append_feedback(
        config.feedback_path, "hn:77", "save", "2026-11-18", _snap("pinned")
    )
    append_feedback(config.feedback_path, "hn:77", "unsave", "2026-11-19", {})
    result, _ = _run(config, tmp_path, monkeypatch)
    html = result.digest_path.read_text(encoding="utf-8")
    assert 'class="block pinned-block"' not in html  # the section itself is gone


def test_run_day_corrupt_feedback_still_delivers(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    config.feedback_path.write_text("{totally corrupt", encoding="utf-8")
    result, _ = _run(config, tmp_path, monkeypatch)
    assert result.exit_code == 0
    assert result.digest_path.exists()


def test_run_day_feedback_nudges_pool_order(tmp_path, monkeypatch):
    """The nudge is SOFT: with equal topic-hit counts and equal points, the item
    matching a DISLIKED topic ranks below the one matching a neutral topic."""
    config = make_config(tmp_path)
    for i in range(4):  # 4 × 0.25 = -1.0 on the NLP topic
        append_feedback(
            config.feedback_path,
            f"hn:x{i}",
            "dislike",
            "2026-11-18",
            {
                "title": f"NLP parsing study {i}",
                "summary": "",
                "url": "https://x.io",
                "source": "arxiv",
            },
        )
    from daily_digest.ranking.heuristic import heuristic_order, score_item

    items = [
        make_item(
            id="hn:a",
            title="LLM RAG pipeline",
            url="https://x.io/a",
            source="hn",
            points=100,
        ),
        make_item(
            id="hn:b",
            title="LLM NLP pipeline",
            url="https://x.io/b",
            source="hn",
            points=100,
        ),
    ]
    signals = read_feedback(config.feedback_path)
    agg = aggregate(signals, "2026-11-19", 14)
    adj = topic_adjustments(agg, config.interests.topics)
    assert adj.get("NLP") == -1.0  # dislikes registered and clamped
    assert adj.get("LLM", 0.0) == 0.0 and adj.get("RAG", 0.0) == 0.0
    # sanity: identical scores without the nudge (same hit count, same points)
    assert abs(score_item(items[0], config) - score_item(items[1], config)) < 1e-9
    order = heuristic_order(items, config, adj)
    assert order[0].title == "LLM RAG pipeline"  # disliked-topic item ranks below
