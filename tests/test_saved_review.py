"""Saved-articles modal bridge + new-only refresh: data, XSS and guards."""

from __future__ import annotations

import json

from daily_digest.feedback import (
    aggregate,
    append_feedback,
    pinned_items,
    read_feedback,
)
from daily_digest.popup_bridge import DigestBridge
from helpers import make_config


DATE = "2026-11-19"


def _snap(title: str, url: str = "https://x.io/item") -> dict:
    return {
        "title": title,
        "url": url,
        "source": "arxiv",
        "summary": f"summary for {title}",
    }


def _bridge(config, date: str = DATE, spawn_fn=None) -> DigestBridge:
    return DigestBridge(
        config,
        {"date": date, "items": {}, "pinned": []},
        spawn_fn=spawn_fn,
    )


def test_saved_items_returns_all_saves_beyond_rail_cap(tmp_path):
    config = make_config(tmp_path)
    for i in range(8):
        append_feedback(
            config.feedback_path, f"arxiv:{i}", "save", DATE, _snap(f"Saved {i}")
        )
    bridge = _bridge(config)

    result = bridge.saved_items()

    assert result["ok"] is True
    assert len(result["items"]) == 8
    # newest save first
    assert result["items"][0]["title"] == "Saved 7"
    agg = aggregate(read_feedback(config.feedback_path), DATE, 14)
    assert len(pinned_items(agg, 5)) == 5  # the rail still caps at 5


def test_saved_items_is_exception_proof(tmp_path, monkeypatch):
    config = make_config(tmp_path)

    def boom(path):
        raise RuntimeError("feedback exploded")

    monkeypatch.setattr("daily_digest.popup_bridge.read_feedback", boom)
    result = _bridge(config).saved_items()

    assert result["ok"] is False
    assert result["items"] == []
    assert "feedback exploded" in result["error"]


def test_saved_items_sanitizes_hrefs(tmp_path):
    config = make_config(tmp_path)
    append_feedback(
        config.feedback_path,
        "x:1",
        "save",
        DATE,
        _snap("js", "javascript:alert(1)"),
    )
    append_feedback(
        config.feedback_path,
        "x:2",
        "save",
        DATE,
        _snap("data", "data:text/html,<script>alert(1)</script>"),
    )
    append_feedback(
        config.feedback_path, "x:3", "save", DATE, _snap("ok", "https://x.io/ok")
    )

    items = {item["uid"]: item for item in _bridge(config).saved_items()["items"]}

    assert items["x:1"]["href"] == "#"
    assert items["x:2"]["href"] == "#"
    assert items["x:3"]["href"] == "https://x.io/ok"


def test_unsave_works_for_old_save_not_in_todays_blob(tmp_path):
    config = make_config(tmp_path)
    append_feedback(
        config.feedback_path, "arxiv:old", "save", "2026-11-18", _snap("Old save")
    )
    bridge = _bridge(config)  # blob has no items/pinned

    result = bridge.feedback("arxiv:old", "unsave")

    assert result["ok"] is True
    assert read_feedback(config.feedback_path)[-1].action == "unsave"
    assert bridge.saved_items()["items"] == []


def test_saved_items_returns_source_label(tmp_path):
    config = make_config(tmp_path)
    append_feedback(config.feedback_path, "arxiv:1", "save", DATE, _snap("One"))
    item = _bridge(config).saved_items()["items"][0]
    assert item["source_label"] == "arXiv"


def test_toggle_save_uses_the_same_button_for_save_and_unsave(tmp_path):
    config = make_config(tmp_path)
    bridge = DigestBridge(
        config,
        {"date": DATE, "items": {"arxiv:1": _snap("Toggle me")}, "pinned": []},
    )

    first = bridge.toggle_save("arxiv:1")
    assert first == {
        "ok": True,
        "uid": "arxiv:1",
        "action": "save",
        "saved": True,
    }
    assert len(bridge.saved_items()["items"]) == 1

    second = bridge.toggle_save("arxiv:1")
    assert second["ok"] is True and second["action"] == "unsave"
    assert second["saved"] is False
    assert bridge.saved_items()["items"] == []


def test_toggle_save_can_unsave_an_old_saved_item(tmp_path):
    config = make_config(tmp_path)
    append_feedback(
        config.feedback_path, "arxiv:old", "save", "2026-11-18", _snap("Old save")
    )
    bridge = _bridge(config)  # blob has no items

    result = bridge.toggle_save("arxiv:old")

    assert result["ok"] is True and result["saved"] is False
    assert bridge.saved_items()["items"] == []


def test_toggle_save_unknown_and_exception_proof(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    bridge = _bridge(config)
    assert bridge.toggle_save("arxiv:missing")["ok"] is False

    def boom(path):
        raise RuntimeError("toggle exploded")

    monkeypatch.setattr("daily_digest.popup_bridge.read_feedback", boom)
    result = _bridge(config).toggle_save("x:1")
    assert result["ok"] is False and "toggle exploded" in result["error"]


def test_undo_unsave_restores_the_saved_item(tmp_path):
    config = make_config(tmp_path)
    append_feedback(
        config.feedback_path,
        "arxiv:old",
        "save",
        "2026-11-19",
        _snap("Restored paper"),
    )
    bridge = _bridge(config)

    assert bridge.feedback("arxiv:old", "unsave")["ok"] is True
    assert bridge.saved_items()["items"] == []
    assert bridge.undo_unsave("arxiv:old")["ok"] is True
    items = bridge.saved_items()["items"]
    assert [item["title"] for item in items] == ["Restored paper"]
    assert read_feedback(config.feedback_path)[-1].action == "save"


def test_undo_unsave_requires_an_unsave_and_is_exception_proof(tmp_path):
    config = make_config(tmp_path)
    bridge = _bridge(config)
    assert bridge.undo_unsave("arxiv:none")["ok"] is False

    append_feedback(config.feedback_path, "arxiv:1", "save", DATE, _snap("Still saved"))
    already = bridge.undo_unsave("arxiv:1")
    assert already["ok"] is False and "already" in already["error"]


def test_undo_unsave_never_raises(tmp_path, monkeypatch):
    config = make_config(tmp_path)

    def boom(path):
        raise RuntimeError("feedback exploded")

    monkeypatch.setattr("daily_digest.popup_bridge.read_feedback", boom)
    result = _bridge(config).undo_unsave("x:1")
    assert result["ok"] is False and "feedback exploded" in result["error"]


def test_ratings_returns_current_state(tmp_path):
    config = make_config(tmp_path)
    append_feedback(config.feedback_path, "a:1", "like", DATE, _snap("Liked"))
    append_feedback(config.feedback_path, "a:2", "dislike", DATE, _snap("Disliked"))
    bridge = DigestBridge(
        config,
        {"date": DATE, "items": {"a:1": _snap("Liked")}, "pinned": []},
    )

    assert bridge.ratings() == {
        "ok": True,
        "ratings": {"a:1": "like", "a:2": "dislike"},
    }
    assert bridge.feedback("a:1", "unlike")["ok"] is True
    assert bridge.ratings()["ratings"] == {"a:2": "dislike"}


def test_ratings_is_exception_proof(tmp_path, monkeypatch):
    config = make_config(tmp_path)

    def boom(path):
        raise RuntimeError("ratings exploded")

    monkeypatch.setattr("daily_digest.popup_bridge.read_feedback", boom)
    result = _bridge(config).ratings()
    assert result["ok"] is False and result["ratings"] == {}


def test_refresh_spawns_new_only_and_guards_double_click(tmp_path):
    config = make_config(tmp_path)
    calls: list[list[str]] = []

    def spawn(args: list[str]) -> bool:
        calls.append(args)
        return True

    bridge = _bridge(config, spawn_fn=spawn)
    first = bridge.refresh()
    second = bridge.refresh()

    assert first == {"ok": True, "spawned": True}
    assert second["ok"] is False and "already" in second["error"]
    assert calls == [["run", "--force", "--new-only"]]


def test_refresh_real_spawn_path_has_exactly_one_module_flag(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    calls: list[list[str]] = []

    class FakePopen:
        def __init__(self, argv, **kwargs):
            calls.append(list(argv))

    monkeypatch.setattr("daily_digest.popup.subprocess.Popen", FakePopen)
    bridge = _bridge(config)  # spawn_fn=None -> real spawn_cli path

    result = bridge.refresh()

    assert result == {"ok": True, "spawned": True}
    assert len(calls) == 1
    assert calls[0][0].endswith("pythonw.exe")
    assert calls[0][1:] == ["-m", "daily_digest", "run", "--force", "--new-only"]
    assert calls[0].count("-m") == 1  # no duplicated module flag


def test_refresh_never_raises_on_spawn_failure(tmp_path):
    config = make_config(tmp_path)

    failed = _bridge(config, spawn_fn=lambda args: False).refresh()
    assert failed["ok"] is False and "spawn" in failed["error"]

    def boom(args: list[str]) -> bool:
        raise RuntimeError("spawn exploded")

    crashed = _bridge(config, spawn_fn=boom).refresh()
    assert crashed["ok"] is False and "spawn exploded" in crashed["error"]


def test_saved_items_response_is_json_serializable(tmp_path):
    config = make_config(tmp_path)
    append_feedback(config.feedback_path, "x:1", "save", DATE, _snap("one"))
    result = _bridge(config).saved_items()
    json.dumps(result)  # pywebview must be able to serialize the response
