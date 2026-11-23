"""Front-page rendered-layout invariants (P3)."""

from __future__ import annotations

import re

from daily_digest.model import RankedItem
from daily_digest.render import render_digest
from helpers import make_config, make_item


def _item(uid: str, section: str, source: str = "arxiv") -> RankedItem:
    return RankedItem(
        item=make_item(
            id=uid,
            title=f"Title {uid}",
            url=f"https://example.test/{uid}",
            source=source,
            points=42,
        ),
        why=f"why {uid}",
        section=section,  # type: ignore[arg-type]
        llm_summary=f"summary {uid}",
    )


def _real_mix() -> list[RankedItem]:
    return [_item(f"p{i}", "papers") for i in range(11)] + [
        _item("t0", "tech_news", "hn")
    ]


def _render(tmp_path, ranked, pinned=(), overview="Tổng hợp hôm nay về agents."):
    config = make_config(tmp_path)
    return render_digest(
        ranked,
        date="2026-11-19",
        mode="llm",
        degraded=False,
        sources_failed=[],
        model_name="glm-5.3",
        template=config.template_path,
        overview=overview,
        overview_label="Tổng hợp hôm nay",
        pinned=list(pinned),
    )


def _section(html: str, key: str) -> str:
    start = html.index(f'class="section-front sec-{key}')
    end = html.index("</section>", start)
    return html[start:end]


def test_every_ranked_item_renders_once_with_feedback(tmp_path):
    ranked = _real_mix()
    html = _render(tmp_path, ranked)
    for item in ranked:
        uid = item.item.id
        assert html.count(f'data-uid="{uid}"') == 1
        assert html.count(f'data-feedback="{uid}|like"') == 1
        assert html.count(f'data-feedback="{uid}|dislike"') == 1
        assert html.count(f'data-feedback="{uid}|save"') == 1
    assert html.count('data-ask="1"') == len(ranked)


def test_overview_keeps_the_final_takeaway_when_it_has_many_points(tmp_path):
    ranked = _real_mix()
    overview = "Một. Hai. Ba. Bốn. Điểm cần nhớ: đọc kỹ."
    html = _render(tmp_path, ranked, overview=overview)

    assert "Điểm cần nhớ: đọc kỹ" in html
    assert "Bốn" not in html  # middle point dropped, final takeaway kept
    assert "overview-point spotlight" in html


def test_most_read_links_point_to_existing_story_anchors(tmp_path):
    ranked = _real_mix()
    html = _render(tmp_path, ranked)
    start = html.index('<section class="most-read">')
    end = html.index("</section>", start)
    rail = html[start:end]
    for item in ranked[2:5]:
        uid = item.item.id
        assert f'href="#story-{uid}"' in rail
        assert f'id="story-{uid}"' in html
    assert "data-feedback" not in rail
    assert "data-ask" not in rail


def test_pinned_block_keeps_locked_class_and_unsave_only(tmp_path):
    pinned = [
        {
            "uid": "saved:1",
            "title": "A saved paper",
            "url": "https://example.test/saved",
            "source": "arxiv",
            "points": None,
            "citations": 7,
            "why": "saved earlier",
            "llm_summary": "",
            "summary": "old abstract",
        }
    ]
    html = _render(tmp_path, _real_mix(), pinned=pinned)
    assert 'class="block pinned-block"' in html
    assert 'data-feedback="saved:1|unsave"' in html
    assert 'data-feedback="saved:1|like"' not in html
    assert 'id="story-saved:1"' in html
    assert 'href="#pinned"' in html  # nav link exists when pinned


def test_nav_omits_pinned_link_without_pinned(tmp_path):
    html = _render(tmp_path, _real_mix())
    assert 'href="#pinned"' not in html
    assert 'class="block pinned-block"' not in html


def test_content_aware_section_variants(tmp_path):
    html = _render(tmp_path, _real_mix())
    papers = _section(html, "papers")
    tech = _section(html, "tech_news")
    tools = _section(html, "tools_releases")
    assert "section-front--grid" in papers
    assert "section-front--band" in tech
    assert "section-front--empty" in tools
    assert "11 bài" in papers
    assert "2 ở trên" in papers
    assert "Hôm nay không có mục nào" in tools
    assert 'id="papers"' in html
    assert 'id="tech-news"' in html
    assert 'id="tools-releases"' in html


def test_split_and_hero_only_variants(tmp_path):
    split = _render(
        tmp_path,
        [
            _item("p0", "papers"),
            _item("p1", "papers"),
            _item("p2", "papers"),
            _item("p3", "papers"),
        ],
    )
    assert "section-front--split" in _section(split, "papers")

    hero_only = _render(
        tmp_path,
        [_item("p0", "papers"), _item("t0", "tech_news", "hn")],
    )
    assert "section-front--hero-only" in _section(hero_only, "papers")
    assert "Bài chính ở trên" in _section(hero_only, "papers")


def test_empty_digest_renders_without_crash(tmp_path):
    html = _render(tmp_path, [], overview="")
    assert "top-fold--empty" in html
    assert html.count("empty-note") >= 3
    assert not re.search(r"<button[^>]*data-feedback=", html)


def _all_in_section(section: str, count: int, source: str) -> list[RankedItem]:
    return [_item(f"{section}:{i}", section, source) for i in range(count)]


def test_more_band_follows_section_body_and_is_labelled(tmp_path):
    html = _render(tmp_path, _all_in_section("papers", 30, "arxiv"))
    papers = _section(html, "papers")
    lead_start = papers.index('class="lead-col"')
    briefs_start = papers.index('class="briefs"')
    band_start = papers.index('class="section-more')

    assert papers.index('class="section-body"') < band_start
    assert briefs_start < band_start
    assert "more-list" not in papers[lead_start:briefs_start]
    assert 'role="group"' in papers
    assert 'id="more-papers"' in papers
    assert 'aria-labelledby="more-papers"' in papers
    assert '<h3 id="more-papers">' in papers


def test_more_band_counts_at_boundaries(tmp_path):
    thirty = _section(
        _render(tmp_path, _all_in_section("papers", 30, "arxiv")), "papers"
    )
    ten = _section(_render(tmp_path, _all_in_section("papers", 10, "arxiv")), "papers")
    nine = _section(_render(tmp_path, _all_in_section("papers", 9, "arxiv")), "papers")

    assert thirty.count('class="story story--feature ') == 1
    assert thirty.count('class="story story--brief ') == 5
    assert (
        thirty.count('class="story story--feature ')
        + thirty.count('class="story story--brief ')
        == 6
    )
    assert thirty.count('class="story story--more ') == 21
    assert thirty.count('class="section-more') == 1
    assert "21 bài" in thirty

    assert ten.count('class="story story--more ') == 1
    assert ten.count('class="section-more') == 1
    assert "1 bài" in ten

    assert nine.count('class="story story--more ') == 0
    assert nine.count('class="section-more') == 0


def test_more_band_keeps_unique_headings_and_interactions(tmp_path):
    ranked = (
        _all_in_section("papers", 10, "arxiv")
        + _all_in_section("tech_news", 10, "hn")
        + _all_in_section("tools_releases", 10, "gh_vllm")
    )
    html = _render(tmp_path, ranked)

    assert html.count('class="section-more') == 3
    for section, key in (
        ("papers", "more-papers"),
        ("tech_news", "more-tech-news"),
        ("tools_releases", "more-tools-releases"),
    ):
        part = _section(html, section)
        assert part.count(f'id="{key}"') == 1
        assert part.count(f'aria-labelledby="{key}"') == 1
    assert html.count('data-ask="1"') == len(ranked)
    assert len(re.findall(r"<button[^>]*data-feedback=", html)) == len(ranked) * 3
    assert html.count('id="story-') == len(ranked)


def test_most_read_rail_has_no_duplicate_feedback(tmp_path):
    ranked = _real_mix()
    html = _render(tmp_path, ranked)
    # 3 feedback buttons per ranked story, no extra feedback from the rail.
    assert len(re.findall(r"<button[^>]*data-feedback=", html)) == len(ranked) * 3
    assert html.count('id="story-') == len(ranked)
