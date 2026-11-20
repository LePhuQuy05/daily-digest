"""Rendered overview references: coverage, links, labels, escaping."""

from __future__ import annotations

from daily_digest.model import RankedItem
from daily_digest.overview import ensure_coverage, parse_overview
from daily_digest.render import render_digest
from helpers import make_config, make_item


def _ranked() -> list[RankedItem]:
    sections = ("papers", "tech_news", "tools_releases", "papers")
    return [
        RankedItem(
            item=make_item(
                id=f"arxiv:2611.{i:05d}",
                title=f"Paper {i}: A useful title",
                url=f"https://arxiv.org/abs/2611.{i:05d}",
                source="arxiv",
            ),
            why=f"why {i}",
            section=sections[i],
        )
        for i in range(4)
    ]


def _render(tmp_path, ranked, overview="", points=()):
    config = make_config(tmp_path)
    return render_digest(
        ranked,
        date="2026-11-19",
        mode="llm",
        degraded=False,
        sources_failed=[],
        model_name="deepseek-v4.1-flash",
        template=config.template_path,
        overview=overview,
        overview_points=points,
    )


def test_structured_overview_renders_inline_chips_and_rest(tmp_path):
    ranked = _ranked()
    text = "Hôm nay [[0]] và [[1]].\n\nĐiểm cần nhớ: [[2]]."
    points = ensure_coverage(parse_overview(text, ranked), ranked)

    html = _render(tmp_path, ranked, overview=text, points=points)

    assert html.count('class="oref"') == 4
    for item in ranked:
        assert f'href="#story-{item.item.id}"' in html
        assert f'data-story-ref="{item.item.id}"' in html
        assert f'title="{item.item.title}"' in html
    assert "Còn lại hôm nay" in html
    assert "overview-rest" in html
    assert "overview-point spotlight" in html
    assert "[[" not in html
    assert 'data-uid="' in html  # story cards still carry data-uid
    assert html.count('data-uid="') == len(ranked)  # chips do not add data-uid
    assert 'tabindex="-1"' in html


def test_structured_overview_escapes_hostile_titles(tmp_path):
    ranked = _ranked()
    ranked[0] = RankedItem(
        item=make_item(
            id="arxiv:evil",
            title="<script>alert(1)</script>",
            url="https://arxiv.org/abs/2611.99999",
            source="arxiv",
        ),
        why="why",
        section="papers",
    )
    text = "Bài [[0]]."
    points = ensure_coverage(parse_overview(text, ranked), ranked)

    html = _render(tmp_path, ranked, overview=text, points=points)

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_legacy_overview_keeps_old_split_path(tmp_path):
    ranked = _ranked()
    html = _render(
        tmp_path,
        ranked,
        overview="Một câu. Hai câu. Ba câu. Bốn câu.",
    )
    assert 'class="oref"' not in html
    assert "Một câu" in html and "Bốn câu" in html


def test_structured_overview_has_no_raw_markers_when_all_invalid(tmp_path):
    ranked = _ranked()
    text = "Bài [[99]] và [[x]]."
    points = ensure_coverage(parse_overview(text, ranked), ranked)

    html = _render(tmp_path, ranked, overview=text, points=points)

    assert "[[" not in html
    assert "Bài" in html
    assert html.count('class="oref"') == len(ranked)  # rest covers all


def test_print_hides_references_and_rest():
    from daily_digest.util import PROJECT_ROOT

    css = (PROJECT_ROOT / "templates" / "newsroom.css.j2").read_text(encoding="utf-8")
    assert ".oref, .overview-rest" in css
    print_block = css[css.index("@media print") :]
    assert ".oref, .overview-rest" in print_block
