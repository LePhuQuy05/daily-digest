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


def test_demo_does_not_need_network_or_a_key(tmp_path, monkeypatch):
    config = make_config(tmp_path)

    def fail(*args, **kwargs):
        raise AssertionError("demo must not perform network I/O")

    monkeypatch.setattr("httpx.Client.send", fail)

    path = render_demo(config, open_browser=False)

    assert "KV Cache Eviction" in path.read_text(encoding="utf-8")
