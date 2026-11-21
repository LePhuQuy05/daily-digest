"""Locale settings bridge: combined apply, backups, archive and latest guard."""

from __future__ import annotations

import json

import daily_digest.popup_bridge as bridge_mod
from daily_digest.popup_bridge import DigestBridge, extract_locale
from daily_digest.render import write_digest
from daily_digest.util import today_str
from helpers import make_config


def _bridge(config, *, date=None, spawn=None, locale="vi", items=None, html_path=None):
    return DigestBridge(
        config,
        {"date": date or today_str(), "items": items or {}, "pinned": []},
        spawn_fn=spawn,
        locale=locale,
        html_path=html_path,
    )


def test_settings_returns_language_choices_and_baked_locale(tmp_path):
    config = make_config(tmp_path)
    result = _bridge(config, locale="ja").settings()
    assert result["ok"] is True
    assert result["language"] == "ja"
    assert result["stored_language"] is None
    assert [item["code"] for item in result["languages"]] == ["vi", "en", "ja"]
    assert result["can_change"] is True

    old = _bridge(config, date="2026-01-01", locale="en").settings()
    assert old["archived"] is True
    assert old["can_change"] is False
    assert old["language"] == "en"


def test_apply_settings_saves_both_backs_up_and_spawns_one(tmp_path):
    config = make_config(tmp_path)
    day = today_str()
    source = config.output_dir / f"digest-{day}.html"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("OLD DIGEST", encoding="utf-8")
    calls: list[list[str]] = []

    result = _bridge(
        config, spawn=lambda args: calls.append(args) or True
    ).apply_settings(16, "ja")

    assert result["ok"] is True
    assert result["saved"] is True
    assert result["spawned"] is True
    assert result["language"] == "ja"
    assert calls == [["run", "--force", "--count", "16", "--lang", "ja"]]
    stored = json.loads(config.preferences_path.read_text(encoding="utf-8"))
    assert stored == {"digest_size": 16, "language": "ja"}
    backup = config.output_dir / f"digest-{day}-morning.html"
    assert backup.read_text(encoding="utf-8") == "OLD DIGEST"


def test_apply_settings_uses_next_unique_backup(tmp_path):
    config = make_config(tmp_path)
    day = today_str()
    source = config.output_dir / f"digest-{day}.html"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("NEW", encoding="utf-8")
    first = config.output_dir / f"digest-{day}-morning.html"
    first.write_text("FIRST", encoding="utf-8")

    result = _bridge(config, spawn=lambda args: True).apply_settings(14, "en")

    assert result["ok"] is True
    second = config.output_dir / f"digest-{day}-morning-2.html"
    assert second.read_text(encoding="utf-8") == "NEW"
    assert first.read_text(encoding="utf-8") == "FIRST"


def test_apply_settings_aborts_when_backup_fails(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    day = today_str()
    source = config.output_dir / f"digest-{day}.html"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("OLD", encoding="utf-8")
    calls: list[list[str]] = []

    def boom(path, output_dir):
        raise OSError("disk full")

    monkeypatch.setattr(bridge_mod, "backup_digest", boom)
    result = _bridge(
        config, spawn=lambda args: calls.append(args) or True
    ).apply_settings(16, "ja")

    assert result["ok"] is False
    assert result["saved"] is False
    assert result["spawned"] is False
    assert "backup failed" in result["error"]
    assert calls == []
    assert not config.preferences_path.exists()


def test_apply_settings_rejects_bad_locale_and_archived_digest(tmp_path):
    config = make_config(tmp_path)
    bridge = _bridge(config, spawn=lambda args: True)
    assert bridge.apply_settings(12, "xx")["ok"] is False
    assert not config.preferences_path.exists()

    old = _bridge(config, date="2026-01-01", spawn=lambda args: True)
    result = old.apply_settings(12, "ja")
    assert result["ok"] is False
    assert result["archived"] is True
    assert not config.preferences_path.exists()


def test_extract_locale_reads_baked_html():
    assert extract_locale('<html lang="ja" dir="ltr">') == "ja"
    assert extract_locale('<html lang="en">') == "en"
    assert extract_locale("<html>") is None


def test_set_language_spawns_localize_once_and_keeps_size(tmp_path):
    config = make_config(tmp_path)
    day = today_str()
    source = config.output_dir / f"digest-{day}.html"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("OLD DIGEST", encoding="utf-8")
    config.preferences_path.write_text(
        json.dumps({"digest_size": 16}), encoding="utf-8"
    )
    calls: list[list[str]] = []
    bridge = _bridge(
        config,
        items={"arxiv:1": {}},
        spawn=lambda args: calls.append(args) or True,
    )

    result = bridge.set_language("ja")

    assert result["ok"] is True
    assert result["saved"] is True
    assert result["spawned"] is True
    assert calls == [
        [
            "localize",
            "--date",
            day,
            "--lang",
            "ja",
            "--expect-count",
            "1",
            "--no-backup",
            "--path",
            str(source),
        ]
    ]
    stored = json.loads(config.preferences_path.read_text(encoding="utf-8"))
    assert stored == {"digest_size": 16, "language": "ja"}
    assert (config.output_dir / f"digest-{day}-morning.html").read_text(
        encoding="utf-8"
    ) == "OLD DIGEST"
    assert len(list(config.output_dir.glob(f"digest-{day}-morning*.html"))) == 1


def test_apply_settings_language_only_uses_current_count_for_short_pool(tmp_path):
    config = make_config(tmp_path)
    day = today_str()
    source = config.output_dir / f"digest-{day}.html"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("OLD", encoding="utf-8")
    config.preferences_path.write_text(
        json.dumps({"digest_size": 12}), encoding="utf-8"
    )
    calls: list[list[str]] = []
    bridge = _bridge(
        config,
        items={f"item:{i}": {} for i in range(10)},
        spawn=lambda args: calls.append(args) or True,
    )

    result = bridge.apply_settings(12, "ja")

    assert result["ok"] is True
    assert result["spawned"] is True
    assert len(calls) == 1
    assert calls[0][0] == "localize"
    assert calls[0][calls[0].index("--expect-count") + 1] == "10"
    assert "run" not in calls[0]


def test_set_language_archived_morning_backup_is_read_only(tmp_path):
    config = make_config(tmp_path)
    day = today_str()
    morning = config.output_dir / f"digest-{day}-morning.html"
    morning.parent.mkdir(parents=True, exist_ok=True)
    morning.write_text("ARCHIVED", encoding="utf-8")
    calls: list[list[str]] = []
    bridge = _bridge(
        config,
        html_path=morning,
        items={"arxiv:1": {}},
        spawn=lambda args: calls.append(args) or True,
    )

    assert bridge.settings()["can_change"] is False
    result = bridge.set_language("ja")
    assert result["ok"] is False
    assert result["archived"] is True
    assert calls == []
    assert morning.read_text(encoding="utf-8") == "ARCHIVED"


def test_set_language_uses_actual_dash_two_path(tmp_path):
    config = make_config(tmp_path)
    day = today_str()
    source = config.output_dir / f"digest-{day}-2.html"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("DASH TWO", encoding="utf-8")
    calls: list[list[str]] = []
    bridge = _bridge(
        config,
        html_path=source,
        items={"arxiv:1": {}},
        spawn=lambda args: calls.append(args) or True,
    )

    result = bridge.set_language("en")

    assert result["ok"] is True
    assert (config.output_dir / f"digest-{day}-2-morning.html").exists()
    assert calls[0][calls[0].index("--path") + 1] == str(source)


def test_set_language_spawn_failure_restores_preference(tmp_path):
    config = make_config(tmp_path)
    day = today_str()
    source = config.output_dir / f"digest-{day}.html"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("OLD", encoding="utf-8")
    config.preferences_path.write_text(
        json.dumps({"digest_size": 12, "language": "vi"}), encoding="utf-8"
    )
    bridge = _bridge(
        config,
        locale="vi",
        items={"arxiv:1": {}},
        spawn=lambda args: False,
    )

    result = bridge.set_language("ja")

    assert result["ok"] is False
    assert result["saved"] is False
    stored = json.loads(config.preferences_path.read_text(encoding="utf-8"))
    assert stored["language"] == "vi"
    assert stored["digest_size"] == 12


def test_set_language_no_op_does_not_backup_or_spawn(tmp_path):
    config = make_config(tmp_path)
    config.preferences_path.write_text(json.dumps({"language": "ja"}), encoding="utf-8")
    calls: list[list[str]] = []
    bridge = _bridge(
        config,
        locale="ja",
        items={"arxiv:1": {}},
        spawn=lambda args: calls.append(args) or True,
    )

    result = bridge.set_language("ja")

    assert result["ok"] is True
    assert result["spawned"] is False
    assert calls == []
    assert not list(config.output_dir.glob("digest-*-morning*.html"))


def test_write_digest_does_not_clobber_latest_on_backfill(tmp_path):
    latest = tmp_path / "latest.html"
    latest.write_text("TODAY", encoding="utf-8")

    write_digest("<html>OLD</html>", tmp_path, "2020-01-01")

    assert latest.read_text(encoding="utf-8") == "TODAY"
    assert (tmp_path / "digest-2020-01-01.html").exists()
