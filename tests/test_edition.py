"""Edition snapshots: render/save/load and pipeline write-only integration."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import daily_digest.pipeline as pipeline
from daily_digest.edition import (
    Edition,
    load_edition,
    render_edition,
    save_edition,
    snapshot_path,
    with_artifact,
)
from daily_digest.i18n import locale_strings
from daily_digest.model import RankedItem
from daily_digest.overview import OverviewPoint, OverviewRef, OverviewSegment
from helpers import FakeLlmClient, llm_ok_json, make_config, make_item


def _ranked(title: str = "A paper title") -> RankedItem:
    item = make_item(
        id="arxiv:2611.00001",
        title=title,
        url="https://arxiv.org/abs/2611.00001",
        source="arxiv",
        summary="Source abstract.",
    )
    return RankedItem(
        item=item,
        why="Vì sao bài này quan trọng.",
        section="papers",
        llm_summary="Bản tóm tắt.",
    )


def _edition() -> Edition:
    ranked = _ranked()
    point = OverviewPoint(
        segments=(
            OverviewSegment(text="Điểm chính: "),
            OverviewSegment(
                ref=OverviewRef(
                    uid=ranked.item.id,
                    label="A paper title",
                    title=ranked.item.title,
                )
            ),
        ),
        kind="takeaway",
    )
    return Edition(
        date="2026-11-21",
        locale="vi",
        ranked=(ranked,),
        mode="llm",
        model_name="test-model",
        degraded=False,
        sources_failed=(),
        overview="Điểm chính: [[0]]",
        overview_points=(point,),
        notice_text="",
        pinned=({"uid": "saved:1", "title": "Saved", "url": "https://x.test"},),
        pinned_overflow=2,
    )


def test_render_edition_and_snapshot_roundtrip(tmp_path):
    config = make_config(tmp_path)
    edition = _edition()

    html = render_edition(edition, config)
    assert '<html lang="vi"' in html
    assert "A paper title" in html
    assert "Vì sao bài này quan trọng." in html
    assert "Bản tóm tắt." in html

    output_dir = tmp_path / "output"
    path = output_dir / "digest-2026-11-21.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    saved = with_artifact(edition, path, html, output_dir)
    sidecar = save_edition(saved, output_dir)
    assert sidecar == snapshot_path(output_dir, "2026-11-21")

    loaded = load_edition(output_dir, "2026-11-21")
    assert loaded is not None
    assert loaded.date == saved.date
    assert loaded.locale == "vi"
    assert loaded.mode == "llm"
    assert loaded.model_name == "test-model"
    assert loaded.degraded is False
    assert loaded.pinned_overflow == 2
    assert loaded.html_relpath == "digest-2026-11-21.html"
    assert loaded.html_sha256 == saved.html_sha256
    assert loaded.edition_id == saved.edition_id
    assert len(loaded.ranked) == 1
    assert loaded.ranked[0].item.published == saved.ranked[0].item.published
    assert loaded.ranked[0].why == saved.ranked[0].why
    assert loaded.ranked[0].llm_summary == saved.ranked[0].llm_summary
    assert loaded.overview_points[0].kind == "takeaway"
    assert loaded.overview_points[0].segments[1].ref is not None
    assert loaded.pinned[0]["uid"] == "saved:1"


def test_unsupported_or_corrupt_snapshot_is_ignored(tmp_path):
    output_dir = tmp_path / "output"
    path = snapshot_path(output_dir, "2026-11-21")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"version": 99, "date": "2026-11-21"}', encoding="utf-8")
    assert load_edition(output_dir, "2026-11-21") is None

    path.write_text("{not json", encoding="utf-8")
    assert load_edition(output_dir, "2026-11-21") is None


def test_published_iso_preserves_wall_clock(tmp_path):
    config = make_config(tmp_path)
    item = make_item(
        id="arxiv:2611.00002",
        title="Date paper",
        url="https://arxiv.org/abs/2611.00002",
        source="arxiv",
    )
    ranked = RankedItem(item=item, why="why", section="papers")
    edition = Edition(
        date="2026-11-21",
        locale="en",
        ranked=(ranked,),
        mode="heuristic",
        model_name="test",
        overview="",
        overview_points=(),
    )
    output_dir = tmp_path / "output"
    html = render_edition(edition, config)
    path = output_dir / "digest-2026-11-21.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    save_edition(with_artifact(edition, path, html, output_dir), output_dir)

    loaded = load_edition(output_dir, "2026-11-21")
    assert loaded is not None
    assert loaded.ranked[0].item.published == item.published
    assert loaded.ranked[0].item.published.tzinfo == timezone.utc


def test_locale_strings_are_sorted_for_deterministic_html():
    keys = list(locale_strings("ja"))
    assert keys == sorted(keys)


def test_run_day_writes_normal_snapshot(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    item = make_item(
        id="arxiv:2611.00003",
        title="Snapshot paper",
        url="https://arxiv.org/abs/2611.00003",
        source="arxiv",
    )
    monkeypatch.setattr(pipeline, "fetch_all", lambda client, cfg: ([item], []))

    result = pipeline.run_day(
        config,
        "2026-11-18",
        llm_client=FakeLlmClient(llm_ok_json(8)),
        notify_fn=lambda *a, **k: None,
    )

    assert result.exit_code == 0
    sidecar = snapshot_path(config.output_dir, "2026-11-18")
    assert sidecar.exists()
    loaded = load_edition(config.output_dir, "2026-11-18")
    assert loaded is not None
    assert len(loaded.ranked) == 1
    assert loaded.html_relpath == "digest-2026-11-18.html"
    assert loaded.html_sha256


def test_run_day_writes_empty_snapshot(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    item = make_item(
        id="hn:1",
        title="Muted",
        url="https://example.test/muted",
        source="hn",
    )
    monkeypatch.setattr(pipeline, "fetch_all", lambda client, cfg: ([item], []))
    monkeypatch.setattr(
        pipeline,
        "apply_mute",
        lambda items, cfg: ([], [(items[0], "test")]),
    )

    result = pipeline.run_day(
        config,
        "2026-11-18",
        notify_fn=lambda *a, **k: None,
    )

    assert result.exit_code == 0
    assert result.mode == "empty"
    loaded = load_edition(config.output_dir, "2026-11-18")
    assert loaded is not None
    assert loaded.ranked == ()
    assert loaded.mode == "empty"
