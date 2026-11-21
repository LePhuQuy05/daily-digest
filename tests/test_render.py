from daily_digest.model import RankedItem
from daily_digest.render import render_digest, write_digest
from helpers import make_config, make_item


def _ranked():
    evil = make_item(
        id="hn:1",
        title="Evil <script>alert(1)</script>",
        url="javascript:alert(1)",
        source="hn",
    )
    good = make_item(
        id="arxiv:2",
        title="Good paper about LLMs",
        url="https://arxiv.org/abs/2",
        source="arxiv",
    )
    return [
        RankedItem(item=evil, why="why <b>bold</b>", section="tech_news"),
        RankedItem(item=good, why="solid LLM content", section="papers"),
    ]


def test_render_escapes_titles_whys_and_filters_hrefs(tmp_path):
    config = make_config(tmp_path)
    html = render_digest(
        _ranked(),
        date="2026-11-18",
        mode="llm",
        degraded=False,
        sources_failed=[],
        model_name="glm-5.3",
        template=config.template_path,
    )
    assert "&lt;script&gt;" in html  # title escaped
    assert "<script>alert" not in html  # no raw script tag
    assert "&lt;b&gt;" in html  # why escaped
    assert 'href="#"' in html  # javascript: url filtered
    assert "Good paper about LLMs" in html
    assert 'href="https://arxiv.org/abs/2"' in html
    assert '<span class="paper-date">18.11.2026</span>' in html
    assert html.count('<span class="paper-date">') == 1  # paper only
    assert "glm-5.3" in html  # model badge
    assert "Nghiên cứu" in html and "Công nghệ" in html


def test_render_degraded_banner(tmp_path):
    config = make_config(tmp_path)
    html = render_digest(
        _ranked(),
        date="2026-11-18",
        mode="heuristic",
        degraded=True,
        sources_failed=["hn"],
        model_name="glm-5.3",
        template=config.template_path,
    )
    assert "degraded" in html and "hn" in html


def test_write_digest_archives_and_updates_latest(tmp_path):
    path = write_digest("<html>hello</html>", tmp_path, "2026-11-18")
    assert path.name == "digest-2026-11-18.html"
    assert path.read_text(encoding="utf-8") == "<html>hello</html>"
    assert (tmp_path / "latest.html").read_text(
        encoding="utf-8"
    ) == "<html>hello</html>"
    assert not (tmp_path / "digest-2026-11-18.html.tmp").exists()  # no temp leftovers


def test_write_digest_locked_target_falls_back(tmp_path, monkeypatch):
    import daily_digest.render as render_mod

    original = render_mod.atomic_write_text

    def fake_write(path, text):
        if path.name == "digest-2026-11-18.html":
            raise PermissionError("file open in browser")
        return original(path, text)

    monkeypatch.setattr(render_mod, "atomic_write_text", fake_write)
    path = write_digest("<html>x</html>", tmp_path, "2026-11-18")
    assert path.name == "digest-2026-11-18-2.html"
    assert path.exists()
    assert (tmp_path / "latest.html").exists()
