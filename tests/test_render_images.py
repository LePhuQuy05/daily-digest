"""Render-level tests: article images on hero, section leads, and briefs."""

from __future__ import annotations

from daily_digest.media import ImageAsset
from daily_digest.model import RankedItem
from daily_digest.overview import heuristic_section_briefs
from daily_digest.render import render_digest
from helpers import make_config, make_item


def _item(uid: str, section: str) -> RankedItem:
    return RankedItem(
        item=make_item(
            id=uid,
            title=f"Title {uid}",
            url=f"https://example.test/{uid}",
            source="arxiv",
        ),
        why=f"why {uid}",
        section=section,  # type: ignore[arg-type]
        llm_summary=f"summary {uid}",
    )


def _render(tmp_path, images=None, with_briefs=False):
    config = make_config(tmp_path)
    ranked = [
        _item("p0", "papers"),
        _item("p1", "papers"),
        _item("p2", "papers"),
        _item("p3", "papers"),
        _item("t0", "tech_news"),
    ]
    return render_digest(
        ranked,
        date="2026-11-19",
        mode="llm",
        degraded=False,
        sources_failed=[],
        model_name="deepseek-v4.1-flash",
        template=config.template_path,
        overview="Tổng hợp hôm nay.",
        overview_label="Tổng hợp hôm nay",
        section_briefs=heuristic_section_briefs(ranked, config) if with_briefs else (),
        images=images,
    )


def _asset(
    uid: str, kind: str = "arxiv_img", width: int = 400, height: int = 240
) -> ImageAsset:
    return ImageAsset(
        uid=uid,
        data_uri="data:image/jpeg;base64,AAAA",
        alt=f"Alt {uid}",
        credit=f"Hình: arXiv:{uid}",
        source_url=f"https://arxiv.org/abs/{uid}",
        kind=kind,
        width=width,
        height=height,
    )


def test_images_on_hero_features_leads_and_briefs(tmp_path):
    html = _render(
        tmp_path,
        images={
            "p0": _asset("p0"),
            "p1": _asset("p1"),  # secondary feature: shown below cover
            "p2": _asset("p2", "arxiv_svg"),  # papers lead: shown
            "p3": _asset("p3"),  # papers brief: shown
        },
        with_briefs=True,
    )
    assert html.count('class="story-media') == 4
    assert html.count('src="data:image/jpeg;base64,AAAA"') == 4
    assert all(f"Alt p{i}" in html for i in range(4))
    assert 'class="story story--feature story--sec-papers story--has-media"' in html
    assert 'class="story story--lead story--sec-papers story--has-media"' in html


def test_portrait_figure_uses_tall_mat(tmp_path):
    html = _render(
        tmp_path,
        images={
            "p0": _asset("p0", width=750, height=1000),
            "p2": _asset("p2"),
        },
    )
    assert (
        html.count('class="story-media story-media--arxiv_img story-media--portrait"')
        == 1
    )
    assert html.count('class="story-media story-media--arxiv_img"') == 1


def test_without_images_keeps_text_layout(tmp_path):
    html = _render(tmp_path, images={})
    assert 'class="story-media' not in html
    assert "story--hero" in html
    assert "section-front" in html
