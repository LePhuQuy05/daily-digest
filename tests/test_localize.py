"""Localize the selected edition: no fetch/rank, target content, fallbacks."""

from __future__ import annotations

import argparse
import json
import re

import daily_digest.media as media_mod
import daily_digest.pipeline as pipeline
import daily_digest.ranking as ranking_mod
from daily_digest.edition import (
    Edition,
    load_edition,
    render_edition,
    save_edition,
    with_artifact,
)
from daily_digest.cli import build_parser, cmd_localize
from daily_digest.localize import localize_edition
from daily_digest.model import RankedItem
from daily_digest.overview import parse_overview
from daily_digest.util import today_str
from helpers import FakeLlmClient, make_config, make_item

WRITER_OK = (
    '{"overview": "Today [[0]]. Key takeaway: keep the source set.", '
    '"items": [{"id": 0, "summary": "English summary."}]}'
)
EDITOR_OK = '{"items": [{"id": 0, "why": "English why."}]}'


def _setup(tmp_path, *, locale="vi"):
    config = make_config(tmp_path)
    date = today_str()
    ranked = [
        RankedItem(
            item=make_item(
                id="arxiv:2611.00001",
                title="Stable paper title",
                url="https://arxiv.org/abs/2611.00001",
                source="arxiv",
                summary="Source abstract.",
            ),
            why="VI sentinel why",
            section="papers",
            llm_summary="VI sentinel summary",
        )
    ]
    points = parse_overview("Tổng quan cũ [[0]]", ranked, "vi")
    edition = Edition(
        date=date,
        locale=locale,
        ranked=tuple(ranked),
        mode="llm",
        model_name="test-model",
        overview="Tổng quan cũ [[0]]",
        overview_points=tuple(points),
    )
    html = render_edition(edition, config)
    output_dir = config.output_dir
    path = output_dir / f"digest-{date}.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    save_edition(with_artifact(edition, path, html, output_dir), output_dir)
    return config, date, ranked[0]


def _fail(*args, **kwargs):
    raise AssertionError("localize must not call the fresh pipeline")


def test_localize_preserves_item_set_and_regenerates_target_locale(
    tmp_path, monkeypatch
):
    config, date, item = _setup(tmp_path)
    monkeypatch.setattr(pipeline, "fetch_all", _fail)
    monkeypatch.setattr(ranking_mod, "select", _fail)
    monkeypatch.setattr(media_mod, "collect_images", _fail)

    result = localize_edition(
        config,
        date,
        "en",
        editor_client=FakeLlmClient(EDITOR_OK),
        writer_client=FakeLlmClient(WRITER_OK),
        backup=False,
    )

    assert result.exit_code == 0
    assert result.mode == "localized"
    assert result.item_count == 1
    html = result.digest_path.read_text(encoding="utf-8")
    assert '<html lang="en"' in html
    assert "English why." in html
    assert "English summary." in html
    assert "VI sentinel why" not in html
    assert "VI sentinel summary" not in html
    assert "Stable paper title" in html
    assert "https://arxiv.org/abs/2611.00001" in html
    assert "18.11.2026" in html
    assert re.findall(r'data-uid="([^"]+)"', html) == [item.item.id]
    assert "Key takeaway:" in html

    saved = load_edition(config.output_dir, date)
    assert saved is not None
    assert saved.locale == "en"
    assert saved.ranked[0].item.id == item.item.id
    assert saved.ranked[0].why == "English why."
    assert saved.ranked[0].llm_summary == "English summary."


def test_localize_without_key_uses_deterministic_fallback(tmp_path):
    config, date, _ = _setup(tmp_path)

    result = localize_edition(config, date, "en", backup=False)

    assert result.exit_code == 1
    assert result.degraded is True
    html = result.digest_path.read_text(encoding="utf-8")
    assert "English why." not in html
    assert "VI sentinel why" not in html
    assert "VI sentinel summary" not in html
    assert "new arXiv" in html  # target-locale heuristic why
    assert '<div class="status-strip notice">Full localization was unavailable' in html
    saved = load_edition(config.output_dir, date)
    assert saved is not None
    assert saved.ranked[0].llm_summary == ""
    assert saved.ranked[0].why != "VI sentinel why"


def test_localize_writer_failure_keeps_target_fallbacks(tmp_path):
    config, date, _ = _setup(tmp_path)

    result = localize_edition(
        config,
        date,
        "en",
        editor_client=FakeLlmClient(EDITOR_OK),
        writer_client=FakeLlmClient(["garbage", "garbage"]),
        backup=False,
    )

    assert result.exit_code == 1
    html = result.digest_path.read_text(encoding="utf-8")
    assert "English why." in html
    assert "English summary." not in html
    assert "VI sentinel summary" not in html
    assert '<div class="status-strip notice">Full localization was unavailable' in html


def test_localize_refuses_count_mismatch_and_archived(tmp_path):
    config, date, _ = _setup(tmp_path)
    result = localize_edition(config, date, "en", expect_count=2, backup=False)
    assert result.exit_code == 2
    assert "expected 2" in result.message

    archived = localize_edition(config, "2026-01-01", "en", backup=False)
    assert archived.exit_code == 2
    assert "read-only" in archived.message


def test_localize_does_not_touch_seen_or_notified(tmp_path):
    config, date, _ = _setup(tmp_path)
    config.state_path.write_text(
        json.dumps(
            {
                "seen": {"arxiv:2611.00001": "2026-11-18"},
                "days": {date: {"notified": True, "digest_path": "old"}},
            }
        ),
        encoding="utf-8",
    )

    result = localize_edition(
        config,
        date,
        "en",
        editor_client=FakeLlmClient(EDITOR_OK),
        writer_client=FakeLlmClient(WRITER_OK),
        backup=False,
    )

    assert result.exit_code == 0
    state = json.loads(config.state_path.read_text(encoding="utf-8"))
    assert state["seen"] == {"arxiv:2611.00001": "2026-11-18"}
    assert state["days"][date]["notified"] is True
    assert state["days"][date]["digest_path"] == str(result.digest_path)


def test_localize_empty_edition_keeps_empty_mode(tmp_path):
    config = make_config(tmp_path)
    date = today_str()
    edition = Edition(
        date=date,
        locale="vi",
        ranked=(),
        mode="empty",
        model_name="test-model",
        overview="",
        overview_points=(),
        notice_text="",
    )
    html = render_edition(edition, config)
    path = config.output_dir / f"digest-{date}.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    save_edition(
        with_artifact(edition, path, html, config.output_dir), config.output_dir
    )

    result = localize_edition(config, date, "en", backup=False)

    assert result.exit_code == 0
    assert result.item_count == 0
    html = result.digest_path.read_text(encoding="utf-8")
    assert '<html lang="en"' in html
    assert '<div class="status-strip notice">' not in html


def test_localize_cli_accepts_locale_and_count_and_dispatches(tmp_path, monkeypatch):
    args = build_parser().parse_args(
        ["localize", "--lang", "ja-JP", "--expect-count", "3"]
    )
    assert args.lang == "ja"
    assert args.expect_count == 3
    assert args.no_backup is False
    assert args.no_popup is False

    config = make_config(tmp_path)
    captured: dict = {}

    monkeypatch.setattr("daily_digest.cli.get_llm_client", lambda cfg: "editor")
    monkeypatch.setattr(
        "daily_digest.cli.get_summarize_client", lambda cfg, editor: "writer"
    )

    def fake_localize(*a, **kwargs):
        captured.update(kwargs)
        from daily_digest.model import RunResult

        return RunResult(exit_code=0, item_count=3, mode="localized")

    monkeypatch.setattr("daily_digest.cli.localize_edition", fake_localize)
    rc = cmd_localize(
        config,
        argparse.Namespace(
            date="2026-11-21",
            lang="ja",
            expect_count=3,
            no_backup=True,
            no_popup=True,
            path=None,
        ),
    )
    assert rc == 0
    assert captured["editor_client"] == "editor"
    assert captured["writer_client"] == "writer"
    assert captured["expect_count"] == 3
    assert captured["backup"] is False
    assert captured["open_popup"] is False
