"""New-only refresh: strict unseen filter, notable backfill, guard and backup."""

from __future__ import annotations

import argparse
import json

import daily_digest.pipeline as pipeline
from daily_digest.cli import build_parser, cmd_run
from daily_digest.model import RunResult
from daily_digest.pipeline import _backup_morning_digest, run_day
from daily_digest.util import save_json
from helpers import FakeLlmClient, llm_ok_json, make_config, make_item


DATE = "2026-11-19"


def _paper(uid: str, title: str):
    return make_item(
        id=f"arxiv:{uid}",
        title=title,
        url=f"https://arxiv.org/abs/{uid}",
        source="arxiv",
        summary=f"abstract for {title}",
    )


def _seed(config, seen: dict[str, str], days: dict | None = None) -> None:
    save_json(config.state_path, {"days": days or {}, "seen": seen})


def _patch(monkeypatch, items):
    monkeypatch.setattr(pipeline, "fetch_all", lambda client, cfg: (items, []))


def test_new_only_drops_same_day_and_previous_seen_then_backfills(
    tmp_path, monkeypatch
):
    config = make_config(tmp_path)
    config.llm.top_n = 6
    items = [
        _paper("2611.10001", "New one"),
        _paper("2611.10002", "New two"),
        _paper("2611.10003", "New three"),
        _paper("2611.10004", "Seen this morning"),
        _paper("2611.10005", "Notable from yesterday"),
    ]
    _seed(
        config,
        {"arxiv:2611.10004": DATE, "arxiv:2611.10005": "2026-11-18"},
    )
    _patch(monkeypatch, items)
    notified: list = []

    result = run_day(
        config,
        DATE,
        llm_client=FakeLlmClient(llm_ok_json(8)),
        force=True,
        new_only=True,
        notify_fn=lambda *a, **k: notified.append(a),
    )

    assert result.exit_code == 0 and result.mode == "llm"
    html = result.digest_path.read_text(encoding="utf-8")
    assert "New one" in html and "New two" in html and "New three" in html
    assert "Notable from yesterday" in html  # backfill: fewer than top_n new
    assert "Seen this morning" not in html  # never re-show today's digest
    state = json.loads(config.state_path.read_text(encoding="utf-8"))
    assert state["seen"]["arxiv:2611.10001"] == DATE
    assert state["seen"]["arxiv:2611.10005"] == DATE  # backfilled today -> seen today


def test_new_only_backfill_fills_to_top_n(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    config.llm.top_n = 5
    items = [
        _paper("2611.10001", "New one"),
        _paper("2611.10002", "New two"),
        _paper("2611.20001", "Prev one"),
        _paper("2611.20002", "Prev two"),
        _paper("2611.20003", "Prev three"),
    ]
    _seed(
        config,
        {
            "arxiv:2611.20001": "2026-11-18",
            "arxiv:2611.20002": "2026-11-17",
            "arxiv:2611.20003": "2026-11-16",
        },
    )
    _patch(monkeypatch, items)

    result = run_day(
        config,
        DATE,
        llm_client=FakeLlmClient(llm_ok_json(8)),
        force=True,
        new_only=True,
        notify_fn=lambda *a, **k: None,
    )

    assert result.exit_code == 0
    assert result.item_count == 5  # 2 unseen + 3 backfilled notable items


def test_new_only_zero_unseen_leaves_state_and_artifacts_untouched(
    tmp_path, monkeypatch
):
    config = make_config(tmp_path)
    items = [_paper("2611.30001", "Seen A"), _paper("2611.30002", "Seen B")]
    _seed(config, {"arxiv:2611.30001": DATE, "arxiv:2611.30002": DATE})
    _patch(monkeypatch, items)
    before = config.state_path.read_bytes()

    result = run_day(
        config,
        DATE,
        llm_client=FakeLlmClient(llm_ok_json(8)),
        force=True,
        new_only=True,
        notify_fn=lambda *a, **k: (_ for _ in ()).throw(AssertionError("notify")),
    )

    assert result.mode == "nothing-new"
    assert result.exit_code == 0
    assert result.digest_path is None
    assert not list(config.output_dir.glob("digest-*.html"))
    assert config.state_path.read_bytes() == before


def test_new_only_backs_up_the_morning_digest_once(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    config.llm.top_n = 3
    config.output_dir.mkdir(parents=True, exist_ok=True)
    morning = config.output_dir / f"digest-{DATE}.html"
    morning.write_text("MORNING EDITION", encoding="utf-8")
    items = [
        _paper("2611.10001", "New one"),
        _paper("2611.10002", "New two"),
        _paper("2611.10003", "New three"),
    ]
    _seed(config, {})
    _patch(monkeypatch, items)

    result = run_day(
        config,
        DATE,
        llm_client=FakeLlmClient(llm_ok_json(8)),
        force=True,
        new_only=True,
        notify_fn=lambda *a, **k: None,
    )

    assert result.exit_code == 0
    backup = config.output_dir / f"digest-{DATE}-morning.html"
    assert backup.read_text(encoding="utf-8") == "MORNING EDITION"
    assert "New one" in morning.read_text(encoding="utf-8")
    # A second backup must never overwrite the first morning copy; it gets -2.
    morning.write_text("EVENING EDITION", encoding="utf-8")
    second = _backup_morning_digest(config.output_dir, DATE)
    assert second is not None
    assert second.name == f"digest-{DATE}-morning-2.html"
    assert second.read_text(encoding="utf-8") == "EVENING EDITION"
    assert backup.read_text(encoding="utf-8") == "MORNING EDITION"


def test_run_cli_accepts_new_only_and_implies_force(tmp_path, monkeypatch):
    args = build_parser().parse_args(["run", "--new-only"])
    assert args.new_only is True

    config = make_config(tmp_path)
    captured: dict = {}

    def fake_run(*a, **kwargs):
        captured.update(kwargs)
        return RunResult(exit_code=0)

    monkeypatch.setattr("daily_digest.cli.run_day", fake_run)
    exit_code = cmd_run(
        config,
        argparse.Namespace(
            date=None,
            force=False,
            new_only=True,
            no_notify=True,
        ),
    )

    assert exit_code == 0
    assert captured["new_only"] is True
    assert captured["force"] is True  # new-only must bypass the delivered-day skip
