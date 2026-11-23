"""Historical backfill, full summaries, and section briefs."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone

import daily_digest.pipeline as pipeline
from daily_digest.cli import cmd_run
from daily_digest.digest_size import save_preferences
from daily_digest.edition import (
    Edition,
    edition_to_dict,
    load_edition,
    save_edition,
    snapshot_path,
)
from daily_digest.model import RankedItem, RunResult
from daily_digest.pipeline import run_day
from helpers import FakeLlmClient, llm_ok_json, make_config, make_item

DATE = "2026-11-23"


def _day(offset: int) -> str:
    base = datetime(2026, 11, 23, tzinfo=timezone.utc)
    return (base - timedelta(days=offset)).strftime("%Y-%m-%d")


def _paper(number: int, title: str, *, source: str = "arxiv") -> object:
    return make_item(
        id=f"arxiv:2611.{number:05d}",
        title=title,
        url=f"https://arxiv.org/abs/2611.{number:05d}",
        source=source,
        summary=f"abstract for {title}",
    )


def _archive(config, date: str, items: list) -> None:
    ranked = tuple(
        RankedItem(item=item, why="archive", section="papers") for item in items
    )
    save_edition(
        Edition(
            date=date,
            locale="vi",
            ranked=ranked,
            mode="llm",
            model_name="archive",
        ),
        config.output_dir,
    )


def _summary_payload(start: int, count: int) -> str:
    return json.dumps(
        {
            "items": [
                {"id": index, "summary": f"SUMMARY-{index}"}
                for index in range(start, start + count)
            ]
        }
    )


def _overview_payload() -> str:
    return json.dumps({"overview": "Theme [[0]].\n\nKey takeaway: read it."})


def _briefs_payload() -> str:
    return json.dumps(
        {
            "sections": [
                {
                    "section": "papers",
                    "text": "Paper brief with a concrete result.",
                    "refs": [0, 1, 2],
                }
            ]
        }
    )


def _summary_client(count: int) -> FakeLlmClient:
    if count <= 16:
        return FakeLlmClient(
            [json.dumps({"overview": "Theme.", "items": []}), _briefs_payload()]
        )
    return FakeLlmClient(
        [
            _summary_payload(0, 12),
            _summary_payload(12, 12),
            _summary_payload(24, count - 24),
            _overview_payload(),
            _briefs_payload(),
        ]
    )


def _seed_seen(config, mapping: dict[str, str]) -> None:
    from daily_digest.util import save_json

    save_json(config.state_path, {"days": {}, "seen": mapping})


def _patch(monkeypatch, items):
    monkeypatch.setattr(pipeline, "fetch_all", lambda client, cfg: (items, []))


def test_eleven_fresh_plus_102_history_fills_thirty(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    save_preferences(config.preferences_path, digest_size=30)
    fresh = [_paper(i, f"Fresh {i}") for i in range(11)]
    yesterday_item = _paper(99999, "Yesterday must not return")
    _archive(config, _day(1), [yesterday_item])
    history: list = []
    seen = {item.id: DATE for item in fresh}
    seen[yesterday_item.id] = _day(1)
    for offset in range(2, 8):
        day_items = [
            _paper(offset * 1000 + i, f"History day {offset} item {i}")
            for i in range(17)
        ]
        history.extend(day_items)
        _archive(config, _day(offset), day_items)
        seen.update({item.id: _day(offset) for item in day_items})
    _archive(
        config,
        _day(2),
        [
            *[_paper(2 * 1000 + i, f"History day 2 item {i}") for i in range(17)],
            yesterday_item,
        ],
    )
    assert len(history) == 102
    _seed_seen(config, seen)
    _patch(monkeypatch, fresh)

    result = run_day(
        config,
        DATE,
        llm_client=FakeLlmClient(llm_ok_json(11)),
        summary_client=_summary_client(30),
        auto_backfill=True,
        notify_fn=lambda *a, **k: None,
    )

    assert result.exit_code == 0
    assert result.item_count == 30
    html = result.digest_path.read_text(encoding="utf-8")
    assert "Yesterday must not return" not in html
    assert html.count("data-uid=") == 30
    assert html.count('class="summary') == 30
    assert html.count('class="ask"') == 30
    assert html.count('data-feedback="arxiv:') == 90
    edition = load_edition(config.output_dir, DATE)
    assert edition is not None
    assert edition.requested_count == 30
    assert edition.backfilled_count == 19
    assert sum(1 for item in edition.ranked if item.backfilled) == 19

    state = json.loads(config.state_path.read_text(encoding="utf-8"))
    assert all(
        uid in state["seen"] for uid in [item.item.id for item in edition.ranked]
    )


def test_backfill_shortfall_is_visible_and_does_not_invent(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    save_preferences(config.preferences_path, digest_size=30)
    fresh = [_paper(i, f"Fresh {i}") for i in range(11)]
    archive_2 = [_paper(100 + i, f"History {i}") for i in range(8)]
    _archive(config, _day(2), archive_2)
    seen = {item.id: DATE for item in fresh}
    seen.update({item.id: _day(2) for item in archive_2})
    _seed_seen(config, seen)
    _patch(monkeypatch, fresh)

    result = run_day(
        config,
        DATE,
        llm_client=FakeLlmClient(llm_ok_json(11)),
        summary_client=None,
        auto_backfill=True,
        notify_fn=lambda *a, **k: None,
    )

    assert result.exit_code == 0
    assert result.item_count == 19
    html = result.digest_path.read_text(encoding="utf-8")
    assert "19/30" in html
    assert html.count("data-uid=") == 19
    edition = load_edition(config.output_dir, DATE)
    assert edition is not None
    assert edition.backfilled_count == 8
    assert edition.requested_count == 30


def test_first_day_shortfall_has_no_backfill(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    save_preferences(config.preferences_path, digest_size=30)
    fresh = [_paper(i, f"First day {i}") for i in range(11)]
    _seed_seen(config, {})
    _patch(monkeypatch, fresh)

    result = run_day(
        config,
        DATE,
        llm_client=FakeLlmClient(llm_ok_json(11)),
        summary_client=None,
        auto_backfill=True,
        notify_fn=lambda *a, **k: None,
    )

    assert result.exit_code == 0
    assert result.item_count == 11
    assert "11/30" in result.digest_path.read_text(encoding="utf-8")
    edition = load_edition(config.output_dir, DATE)
    assert edition is not None and edition.backfilled_count == 0


def test_no_backfill_when_target_is_met(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    fresh = [_paper(i, f"Fresh {i}") for i in range(30)]
    _seed_seen(config, {})
    _patch(monkeypatch, fresh)

    result = run_day(
        config,
        DATE,
        llm_client=FakeLlmClient(llm_ok_json(1)),
        summary_client=None,
        auto_backfill=True,
        target=1,
        notify_fn=lambda *a, **k: None,
    )

    assert result.item_count == 1
    edition = load_edition(config.output_dir, DATE)
    assert edition is not None and edition.backfilled_count == 0


def test_cmd_run_enables_auto_backfill_from_saved_size(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    save_preferences(config.preferences_path, digest_size=30)
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
            new_only=False,
            backfill=False,
            no_backfill=False,
            no_notify=True,
        ),
    )

    assert exit_code == 0
    assert captured["auto_backfill"] is True
    assert captured["backfill"] is False


def test_backfilled_flag_survives_sidecar_roundtrip(tmp_path):
    config = make_config(tmp_path)
    item = _paper(1, "Backfilled paper")
    edition = Edition(
        date=DATE,
        locale="vi",
        ranked=(RankedItem(item=item, why="older", section="papers", backfilled=True),),
        mode="llm",
        model_name="test",
        requested_count=30,
        backfilled_count=1,
    )
    save_edition(edition, config.output_dir)

    loaded = load_edition(config.output_dir, DATE)

    assert loaded is not None
    assert loaded.ranked[0].backfilled is True
    assert loaded.requested_count == 30
    assert loaded.backfilled_count == 1
    assert "backfilled" in edition_to_dict(edition)["ranked"][0]


def test_no_backfill_suppresses_new_only_history(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    fresh = [_paper(i, f"Fresh {i}") for i in range(2)]
    history = [_paper(100 + i, f"History {i}") for i in range(3)]
    _archive(config, _day(2), history)
    seen = {item.id: _day(2) for item in history}
    _seed_seen(config, seen)
    _patch(monkeypatch, fresh)

    result = run_day(
        config,
        DATE,
        llm_client=FakeLlmClient(llm_ok_json(2)),
        summary_client=None,
        new_only=True,
        allow_backfill=False,
        target=5,
        notify_fn=lambda *a, **k: None,
    )

    assert result.item_count == 2
    html = result.digest_path.read_text(encoding="utf-8")
    assert "History 0" not in html


def test_bad_counts_do_not_hide_a_valid_snapshot(tmp_path):
    config = make_config(tmp_path)
    edition = Edition(
        date=DATE,
        locale="vi",
        ranked=(RankedItem(item=_paper(1, "Valid"), why="why", section="papers"),),
        mode="llm",
        model_name="test",
        requested_count=30,
        backfilled_count=2,
    )
    save_edition(edition, config.output_dir)
    path = snapshot_path(config.output_dir, DATE)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["requested_count"] = "not-a-number"
    payload["backfilled_count"] = None
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_edition(config.output_dir, DATE)

    assert loaded is not None
    assert loaded.requested_count == 0
    assert loaded.backfilled_count == 0


def test_backfill_applies_mute_and_dedupes_history(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    save_preferences(config.preferences_path, digest_size=30)
    config.interests.mute = ["MUTED"]
    fresh = [_paper(i, f"Fresh {i}") for i in range(11)]
    archive_2 = [_paper(100 + i, f"History two {i}") for i in range(10)]
    archive_3 = [_paper(200 + i, f"History three {i}") for i in range(10)]
    muted = _paper(9999, "MUTED history item")
    duplicate = archive_2[0]
    archive_2.append(muted)
    archive_3.append(duplicate)
    _archive(config, _day(2), archive_2)
    _archive(config, _day(3), archive_3)
    seen = {item.id: DATE for item in fresh}
    seen.update({item.id: _day(2) for item in archive_2})
    seen.update({item.id: _day(3) for item in archive_3})
    _seed_seen(config, seen)
    _patch(monkeypatch, fresh)

    result = run_day(
        config,
        DATE,
        llm_client=FakeLlmClient(llm_ok_json(11)),
        summary_client=None,
        auto_backfill=True,
        notify_fn=lambda *a, **k: None,
    )

    assert result.exit_code == 0
    assert result.item_count == 30
    html = result.digest_path.read_text(encoding="utf-8")
    assert "MUTED history item" not in html
    assert html.count(f'data-uid="{duplicate.id}"') == 1
    edition = load_edition(config.output_dir, DATE)
    assert edition is not None
    assert edition.backfilled_count == 19
    assert len({item.item.id for item in edition.ranked}) == 30
