"""Locale resolution reaches the rendered pipeline artifact."""

from __future__ import annotations

import json

import daily_digest.pipeline as pipeline
from daily_digest.pipeline import run_day
from helpers import make_config, make_item


def _items():
    return [
        make_item(
            id="hn:1",
            title="A news title",
            url="https://example.com/a",
            source="hn",
            points=100,
        ),
        make_item(
            id="arxiv:2611.00001",
            title="A paper title",
            url="https://arxiv.org/abs/2611.00001",
            source="arxiv",
        ),
    ]


def _patch_fetch(monkeypatch):
    monkeypatch.setattr(pipeline, "fetch_all", lambda client, config: (_items(), []))


def _notify(counts, path, cfg):
    return None


def test_stored_language_drives_rendered_chrome(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    config.preferences_path.write_text(json.dumps({"language": "ja"}), encoding="utf-8")
    _patch_fetch(monkeypatch)

    result = run_day(config, "2026-11-18", notify_fn=_notify)

    assert result.digest_path is not None
    html = result.digest_path.read_text(encoding="utf-8")
    assert '<html lang="ja" dir="ltr">' in html
    assert "2026年11月18日（水）" in html
    assert "論文" in html


def test_language_override_beats_stored_preference(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    config.preferences_path.write_text(json.dumps({"language": "ja"}), encoding="utf-8")
    _patch_fetch(monkeypatch)

    result = run_day(config, "2026-11-18", language="en", notify_fn=_notify)

    assert result.digest_path is not None
    html = result.digest_path.read_text(encoding="utf-8")
    assert '<html lang="en" dir="ltr">' in html
    assert "WEDNESDAY, 18.11.2026" in html
    stored = json.loads(config.preferences_path.read_text(encoding="utf-8"))
    assert stored["language"] == "ja"  # one-off override, not persisted
