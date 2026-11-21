"""Zero-key demo renders the real template from bundled fixtures."""

from __future__ import annotations

from daily_digest.demo import render_demo
from helpers import make_config


def test_demo_renders_offline_digest_with_coverage(tmp_path):
    config = make_config(tmp_path)

    path = render_demo(config, open_browser=False)

    assert path == tmp_path / "output" / "demo.html"
    assert path.exists()
    html = path.read_text(encoding="utf-8")
    assert "Chế độ demo" in html
    assert "Biên tập: demo" in html
    assert html.count('class="oref"') >= 9
    assert "Còn lại hôm nay" in html
    assert "[[" not in html
    assert html.count('data-uid="') == 9
    assert 'story--cover"' in html
    assert 'class="story-credit"' in html
    assert "Ảnh: demo fixture" in html


def test_demo_japanese_locale(tmp_path):
    config = make_config(tmp_path)

    path = render_demo(config, locale="ja", open_browser=False)

    html = path.read_text(encoding="utf-8")
    assert '<html lang="ja" dir="ltr">' in html
    assert "AIニュース" in html
    assert "論文" in html
    assert "要点:" in html
    assert "Chế độ demo" not in html


def test_demo_writes_all_locale_files_for_ui_switcher(tmp_path):
    import argparse

    from daily_digest.cli import cmd_demo

    config = make_config(tmp_path)
    assert cmd_demo(config, argparse.Namespace(lang="ja", no_open=True)) == 0
    for locale in ("vi", "en", "ja"):
        path = config.output_dir / f"demo-{locale}.html"
        html = path.read_text(encoding="utf-8")
        assert f'<html lang="{locale}" dir="ltr">' in html
        assert 'id="lang-switch"' in html
        assert f'<option value="{locale}" selected>' in html


def test_demo_does_not_need_network_or_a_key(tmp_path, monkeypatch):
    config = make_config(tmp_path)

    def fail(*args, **kwargs):
        raise AssertionError("demo must not perform network I/O")

    monkeypatch.setattr("httpx.Client.send", fail)

    path = render_demo(config, open_browser=False)

    assert "KV Cache Eviction" in path.read_text(encoding="utf-8")
