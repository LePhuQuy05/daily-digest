"""Edition snapshots: render/save/load and pipeline write-only integration."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import daily_digest.pipeline as pipeline
from daily_digest.edition import (
    Edition,
    edition_from_legacy_html,
    extract_images_from_html,
    load_edition,
    render_edition,
    save_edition,
    snapshot_path,
    with_artifact,
)
from daily_digest.i18n import locale_strings
from daily_digest.media import ImageAsset
from daily_digest.model import RankedItem
from daily_digest.overview import (
    OverviewPoint,
    OverviewRef,
    OverviewSegment,
    SectionBrief,
)
from daily_digest.util import PROJECT_ROOT
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


def _legacy_html(tmp_path, *, locale="vi"):
    config = make_config(tmp_path)
    ranked = _ranked()
    image = ImageAsset(
        uid=ranked.item.id,
        data_uri="data:image/jpeg;base64,AAAA",
        alt="Cover alt",
        credit="Ảnh: test",
        source_url="https://example.test/image",
        kind="og",
        width=1200,
        height=630,
    )
    edition = Edition(
        date="2026-11-21",
        locale=locale,
        ranked=(ranked,),
        mode="llm",
        model_name="test-model",
        overview="Điểm chính: [[0]]",
        overview_points=(),
        images={ranked.item.id: image},
    )
    html = render_edition(edition, config)
    output_dir = tmp_path / "output"
    path = output_dir / f"digest-{edition.date}.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return html, path, output_dir, config, ranked


def test_legacy_edition_preserves_order_date_and_cover_image(tmp_path):
    html, path, output_dir, config, ranked = _legacy_html(tmp_path)
    assert "story--cover" in html  # fixture must exercise the cover image

    legacy = edition_from_legacy_html(html, path, config, output_dir)
    assert legacy is not None
    assert legacy.locale == "vi"
    assert len(legacy.ranked) == 1
    assert legacy.ranked[0].item.id == ranked.item.id
    assert legacy.ranked[0].why == ranked.why
    assert legacy.ranked[0].section == "papers"
    assert legacy.ranked[0].item.published is not None
    assert legacy.ranked[0].item.published.year == 2026
    assert legacy.ranked[0].item.published.month == 11
    assert legacy.ranked[0].item.published.day == 18
    assert legacy.images[ranked.item.id].data_uri.startswith("data:image/")
    assert legacy.html_relpath == "digest-2026-11-21.html"
    assert legacy.html_sha256


def test_legacy_edition_reads_japanese_paper_date(tmp_path):
    html, path, output_dir, config, _ = _legacy_html(tmp_path, locale="ja")

    legacy = edition_from_legacy_html(html, path, config, output_dir)
    assert legacy is not None
    assert legacy.locale == "ja"
    published = legacy.ranked[0].item.published
    assert published is not None
    assert (published.year, published.month, published.day) == (2026, 11, 18)


def test_legacy_extraction_requires_digest_data(tmp_path):
    config = make_config(tmp_path)
    path = tmp_path / "output" / "digest-2026-11-21.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("<html><body>old digest</body></html>", encoding="utf-8")
    assert (
        edition_from_legacy_html(path.read_text(encoding="utf-8"), path, config) is None
    )


def test_rendered_html_hash_is_deterministic_across_hash_seeds():
    script = r"""
from datetime import datetime, timezone
import hashlib
from daily_digest.config import Config
from daily_digest.edition import Edition, render_edition
from daily_digest.model import Item, RankedItem

item = Item(
    id="arxiv:1", title="Deterministic title", url="https://example.test/1",
    source="arxiv", published=datetime(2026, 11, 18, tzinfo=timezone.utc),
    summary="Abstract",
)
ranked = RankedItem(item=item, why="why", section="papers", llm_summary="summary")
edition = Edition(
    date="2026-11-21", locale="vi", ranked=(ranked,), mode="llm",
    model_name="test-model", overview="Tổng hợp [[0]]", overview_points=(),
)
html = render_edition(edition, Config())
print(hashlib.sha256(html.encode("utf-8")).hexdigest())
"""
    hashes = []
    for seed in ("1", "2"):
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = seed
        output = subprocess.check_output(
            [sys.executable, "-c", script],
            cwd=str(PROJECT_ROOT),
            env=env,
            text=True,
        )
        hashes.append(output.strip())
    assert hashes[0] == hashes[1]


def test_section_brief_segments_roundtrip_and_old_snapshot(tmp_path):
    config = make_config(tmp_path)
    item = make_item(
        id="arxiv:2611.00441",
        title="Segment paper",
        url="https://arxiv.org/abs/2611.00441",
        source="arxiv",
        summary="abstract",
    )
    ref = OverviewRef(uid=item.id, label="Segment", title=item.title)
    brief = SectionBrief(
        section="papers",
        text="Old text",
        refs=(ref,),
        coverage_refs=(),
        segments=(
            OverviewSegment(text="Paper: "),
            OverviewSegment(ref=ref),
            OverviewSegment(text="."),
        ),
    )
    edition = Edition(
        date="2026-11-23",
        locale="vi",
        ranked=(RankedItem(item=item, why="why", section="papers"),),
        mode="llm",
        model_name="test",
        section_briefs=(brief,),
    )
    save_edition(edition, config.output_dir)
    loaded = load_edition(config.output_dir, "2026-11-23")
    assert loaded is not None
    assert loaded.section_briefs[0].segments[1].ref.uid == item.id
    assert loaded.section_briefs[0].segments[0].text == "Paper: "

    path = snapshot_path(config.output_dir, "2026-11-23")
    payload = json.loads(path.read_text(encoding="utf-8"))
    del payload["section_briefs"][0]["segments"]
    path.write_text(json.dumps(payload), encoding="utf-8")
    old = load_edition(config.output_dir, "2026-11-23")
    assert old is not None
    assert old.section_briefs[0].segments == ()
    assert old.section_briefs[0].text == "Old text"
