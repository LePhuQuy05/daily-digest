"""Target-count integration: CLI, preferences, short pools and backup."""

from __future__ import annotations

import argparse
import json

import pytest

import daily_digest.pipeline as pipeline
from daily_digest.cli import build_parser, cmd_run
from daily_digest.digest_size import save_digest_size
from daily_digest.model import RunResult
from helpers import FakeLlmClient, llm_ok_json, make_config, make_item

DATE = "2026-11-21"


def _items(count: int = 20):
    return [
        make_item(
            id=f"arxiv:2611.{i:05d}",
            title=f"Paper {i}",
            url=f"https://arxiv.org/abs/2611.{i:05d}",
            source="arxiv",
            summary=f"abstract {i}",
        )
        for i in range(count)
    ]


def _patch(monkeypatch, items):
    monkeypatch.setattr(pipeline, "fetch_all", lambda client, cfg: (items, []))


def _run(config, *, target=None, force=True):
    return pipeline.run_day(
        config,
        DATE,
        llm_client=FakeLlmClient(llm_ok_json(30)),
        force=force,
        notify_fn=lambda *a, **k: None,
        target=target,
    )


def test_run_day_uses_target_and_updates_seen(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    _patch(monkeypatch, _items(20))

    result = _run(config, target=16)

    assert result.exit_code == 0
    assert result.item_count == 16
    html = result.digest_path.read_text(encoding="utf-8")
    assert html.count('data-uid="') == 16
    state = json.loads(config.state_path.read_text(encoding="utf-8"))
    assert len(state["seen"]) == 16


def test_stored_preference_applies_without_cli_override(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    save_digest_size(config.preferences_path, 16)
    _patch(monkeypatch, _items(20))

    result = _run(config, target=None)

    assert result.item_count == 16


def test_cli_count_is_one_off_and_implies_force(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    save_digest_size(config.preferences_path, 16)
    captured: dict = {}

    def fake_run(*a, **kwargs):
        captured.update(kwargs)
        return RunResult(exit_code=0)

    monkeypatch.setattr("daily_digest.cli.run_day", fake_run)
    args = argparse.Namespace(
        date=None, force=False, new_only=False, no_notify=True, count=5
    )

    assert cmd_run(config, args) == 0
    assert captured["target"] == 5
    assert captured["force"] is True
    assert (
        json.loads(config.preferences_path.read_text(encoding="utf-8"))["digest_size"]
        == 16
    )


def test_cli_count_rejects_out_of_range():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["run", "--count", "0"])
    with pytest.raises(SystemExit):
        build_parser().parse_args(["run", "--count", "31"])
    with pytest.raises(SystemExit):
        build_parser().parse_args(["run", "--count", "abc"])


def test_forced_rebuild_backs_up_morning_edition(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    morning = config.output_dir / f"digest-{DATE}.html"
    morning.write_text("MORNING EDITION", encoding="utf-8")
    _patch(monkeypatch, _items(20))

    result = _run(config, target=8)

    backup = config.output_dir / f"digest-{DATE}-morning.html"
    assert result.exit_code == 0
    assert backup.read_text(encoding="utf-8") == "MORNING EDITION"
    assert result.digest_path.read_text(encoding="utf-8") != "MORNING EDITION"


def test_default_remains_12(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    _patch(monkeypatch, _items(20))

    result = _run(config, target=None)

    assert result.item_count == 12


def test_run_budget_skips_writer_and_still_ships(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    _patch(monkeypatch, _items(20))
    monkeypatch.setattr(pipeline, "RUN_BUDGET_SECONDS", 0)
    writer = FakeLlmClient('{"overview": "should not run", "items": []}')

    result = pipeline.run_day(
        config,
        DATE,
        llm_client=FakeLlmClient(llm_ok_json(12)),
        summary_client=writer,
        force=True,
        notify_fn=lambda *a, **k: None,
        target=12,
    )

    assert result.exit_code == 0
    assert writer.chat.calls == []
    assert result.digest_path.exists()
    assert "Paper 0" in result.digest_path.read_text(encoding="utf-8")
