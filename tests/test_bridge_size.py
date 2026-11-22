"""DigestBridge size API: bounds, persistence, spawn, archive and cooldown."""

from __future__ import annotations

import json

import daily_digest.popup_bridge as bridge_mod
from daily_digest.digest_size import save_digest_size
from daily_digest.popup_bridge import DigestBridge
from daily_digest.util import today_str
from helpers import make_config


def _bridge(config, *, date=None, spawn=None):
    return DigestBridge(
        config,
        {"date": date or today_str(), "items": {}, "pinned": []},
        spawn_fn=spawn,
    )


def test_digest_size_defaults_for_today_and_archived(tmp_path):
    config = make_config(tmp_path)
    today = _bridge(config)
    result = today.digest_size()
    assert result["ok"] is True
    assert result["size"] == 12
    assert result["default"] == 12
    assert result["min"] == 1
    assert result["max"] == 30
    assert result["stored"] is None
    assert result["current"] == 0
    assert result["can_change"] is True
    assert result["archived"] is False

    old = _bridge(config, date="2026-01-01").digest_size()
    assert old["ok"] is True
    assert old["can_change"] is False
    assert old["archived"] is True


def test_set_size_saves_and_spawns_exact_args(tmp_path):
    config = make_config(tmp_path)
    calls: list[list[str]] = []
    bridge = _bridge(config, spawn=lambda args: calls.append(args) or True)

    result = bridge.set_digest_size(16)

    assert result["ok"] is True
    assert result["saved"] is True
    assert result["spawned"] is True
    assert result["size"] == 16
    assert calls == [["run", "--force", "--count", "16", "--backfill"]]
    assert (
        json.loads(config.preferences_path.read_text(encoding="utf-8"))["digest_size"]
        == 16
    )


def test_set_size_is_idempotent_without_spawning(tmp_path):
    config = make_config(tmp_path)
    save_digest_size(config.preferences_path, 12)
    calls: list[list[str]] = []
    bridge = _bridge(config, spawn=lambda args: calls.append(args) or True)
    bridge.items = {f"item:{i}": {} for i in range(12)}

    result = bridge.set_digest_size(12)

    assert result["ok"] is True
    assert result["spawned"] is False
    assert calls == []

    # Stored preference is already 12, but the visible digest has 9 items:
    # applying 12 must rebuild it.
    bridge.items = {f"item:{i}": {} for i in range(9)}
    rerun = bridge.set_digest_size(12)
    assert rerun["ok"] is True
    assert rerun["spawned"] is True
    assert calls == [["run", "--force", "--count", "12", "--backfill"]]


def test_archived_digest_refuses_size_change(tmp_path):
    config = make_config(tmp_path)
    calls: list[list[str]] = []
    bridge = _bridge(
        config, date="2026-01-01", spawn=lambda args: calls.append(args) or True
    )

    result = bridge.set_digest_size(16)

    assert result["ok"] is False
    assert result["archived"] is True
    assert result["saved"] is False
    assert calls == []
    assert not config.preferences_path.exists()


def test_size_bounds_and_cap(tmp_path):
    config = make_config(tmp_path)
    config.llm.max_pool = 10
    bridge = _bridge(config, spawn=lambda args: True)

    assert bridge.digest_size()["max"] == 10
    assert bridge.set_digest_size(0)["ok"] is False
    assert bridge.set_digest_size(11)["ok"] is False
    assert bridge.set_digest_size(10)["ok"] is True


def test_spawn_failure_keeps_saved_preference(tmp_path):
    config = make_config(tmp_path)
    bridge = _bridge(config, spawn=lambda args: False)

    result = bridge.set_digest_size(16)

    assert result["ok"] is False
    assert result["saved"] is True
    assert result["spawned"] is False
    assert "preference saved" in result["error"]
    assert (
        json.loads(config.preferences_path.read_text(encoding="utf-8"))["digest_size"]
        == 16
    )


def test_save_failure_does_not_spawn(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    calls: list[list[str]] = []

    def boom(path, size):
        raise OSError("disk full")

    monkeypatch.setattr(bridge_mod, "save_digest_size", boom)
    bridge = _bridge(config, spawn=lambda args: calls.append(args) or True)

    result = bridge.set_digest_size(16)

    assert result["ok"] is False
    assert result["saved"] is False
    assert result["spawned"] is False
    assert calls == []


def test_shared_cooldown_between_refresh_and_size(tmp_path):
    config = make_config(tmp_path)
    calls: list[list[str]] = []
    bridge = _bridge(config, spawn=lambda args: calls.append(args) or True)

    assert bridge.set_digest_size(16)["spawned"] is True
    second = bridge.refresh()

    assert second["ok"] is False
    assert "already refreshing" in second["error"]
    assert len(calls) == 1


def test_reset_removes_only_preference(tmp_path):
    config = make_config(tmp_path)
    config.preferences_path.write_text(
        json.dumps({"digest_size": 18, "theme": "dark"}), encoding="utf-8"
    )
    bridge = _bridge(config)

    result = bridge.reset_digest_size()

    assert result["ok"] is True
    assert result["size"] == 12
    assert result["stored"] is None
    assert json.loads(config.preferences_path.read_text(encoding="utf-8")) == {
        "theme": "dark"
    }
