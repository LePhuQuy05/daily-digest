"""Front-page layout model — pure tests, no Jinja/template involvement."""

from __future__ import annotations

from daily_digest.frontpage import build_front_page
from daily_digest.model import SECTIONS, RankedItem
from daily_digest.render import _format_date_long
from helpers import make_item


def _ranked_item(uid: str, section: str, source: str = "arxiv") -> RankedItem:
    return RankedItem(
        item=make_item(
            id=uid,
            title=f"Title {uid}",
            url=f"https://example.test/{uid}",
            source=source,
        ),
        why=f"why {uid}",
        section=section,  # type: ignore[arg-type]
        llm_summary=f"summary {uid}",
    )


def _real_mix() -> list[RankedItem]:
    """The real 2026-11-19 shape: 11 papers + 1 tech, zero tools/pinned."""
    return [_ranked_item(f"p{i}", "papers") for i in range(11)] + [
        _ranked_item("t0", "tech_news", "hn")
    ]


class TestFrontPageRealShape:
    def test_hero_is_top_ranked(self):
        ranked = _real_mix()
        page = build_front_page(ranked)
        assert page.lead is ranked[0]
        assert page.lead.item.id == "p0"

    def test_sections_are_all_three_in_model_order(self):
        page = build_front_page(_real_mix())
        assert tuple(s.key for s in page.sections) == SECTIONS

    def test_papers_lead_and_briefs_after_hero(self):
        page = build_front_page(_real_mix())
        papers = next(s for s in page.sections if s.key == "papers")
        assert papers.total == 11
        assert page.secondary is not None and page.secondary.item.id == "p1"
        assert papers.lead is not None and papers.lead.item.id == "p2"
        assert [b.item.id for b in papers.briefs] == [f"p{i}" for i in range(3, 11)]

    def test_secondary_is_second_ranked(self):
        ranked = _real_mix()
        page = build_front_page(ranked)
        assert page.secondary is ranked[1]

    def test_one_item_section_becomes_band_lead(self):
        page = build_front_page(_real_mix())
        tech = next(s for s in page.sections if s.key == "tech_news")
        assert tech.total == 1
        assert tech.lead is not None and tech.lead.item.id == "t0"
        assert tech.briefs == ()

    def test_empty_section_is_total(self):
        page = build_front_page(_real_mix())
        tools = next(s for s in page.sections if s.key == "tools_releases")
        assert tools.total == 0
        assert tools.lead is None
        assert tools.briefs == ()

    def test_most_read_uses_five_after_hero_and_secondary(self):
        ranked = _real_mix()
        page = build_front_page(ranked)
        assert page.most_read == tuple(ranked[2:7])

    def test_source_counts_raw_keys(self):
        page = build_front_page(_real_mix())
        assert page.source_counts == {"arxiv": 11, "hn": 1}

    def test_every_item_renders_once(self):
        ranked = _real_mix()
        page = build_front_page(ranked)
        rendered = []
        if page.lead:
            rendered.append(page.lead)
        if page.secondary:
            rendered.append(page.secondary)
        for section in page.sections:
            if section.lead:
                rendered.append(section.lead)
            rendered.extend(section.briefs)
        ids = [r.item.id for r in rendered]
        assert len(ids) == len(set(ids)) == 12
        assert set(ids) == {r.item.id for r in ranked}

    def test_hero_not_duplicated_in_its_section(self):
        page = build_front_page(_real_mix())
        papers = next(s for s in page.sections if s.key == "papers")
        section_ids = {papers.lead.item.id} | {b.item.id for b in papers.briefs}
        assert page.lead.item.id not in section_ids


class TestFrontPageEdgeCases:
    def test_empty_digest(self):
        page = build_front_page([])
        assert page.lead is None
        assert page.secondary is None
        assert tuple(s.key for s in page.sections) == SECTIONS
        assert all(
            s.lead is None and s.briefs == () and s.total == 0 for s in page.sections
        )
        assert page.most_read == ()
        assert page.source_counts == {}

    def test_single_item_hero_only(self):
        ranked = [_ranked_item("only", "papers")]
        page = build_front_page(ranked)
        papers = next(s for s in page.sections if s.key == "papers")
        assert page.lead is not None and page.lead.item.id == "only"
        assert page.secondary is None
        assert papers.total == 1
        assert papers.lead is None
        assert papers.briefs == ()
        assert page.most_read == ()

    def test_two_items_same_section_hero_plus_secondary(self):
        ranked = [_ranked_item("a", "papers"), _ranked_item("b", "papers")]
        page = build_front_page(ranked)
        papers = next(s for s in page.sections if s.key == "papers")
        assert page.lead.item.id == "a"
        assert page.secondary.item.id == "b"
        assert papers.total == 2
        assert papers.lead is None
        assert papers.briefs == ()
        assert page.most_read == ()

    def test_order_is_preserved_not_reranked(self):
        ranked = [
            _ranked_item("a", "papers"),
            _ranked_item("b", "tech_news", "hn"),
            _ranked_item("c", "papers"),
            _ranked_item("d", "tools_releases"),
            _ranked_item("e", "papers"),
        ]
        page = build_front_page(ranked)
        papers = next(s for s in page.sections if s.key == "papers")
        tech = next(s for s in page.sections if s.key == "tech_news")
        tools = next(s for s in page.sections if s.key == "tools_releases")
        assert page.lead.item.id == "a"
        assert page.secondary.item.id == "b"
        assert papers.total == 3
        assert papers.lead.item.id == "c"
        assert [b.item.id for b in papers.briefs] == ["e"]
        assert tech.total == 1
        assert tech.lead is None
        assert tools.lead.item.id == "d"
        assert page.most_read == tuple(ranked[2:7])

    def test_section_with_only_lead_and_secondary_above(self):
        ranked = [_ranked_item("hero", "papers"), _ranked_item("t", "tech_news", "hn")]
        page = build_front_page(ranked)
        papers = next(s for s in page.sections if s.key == "papers")
        tech = next(s for s in page.sections if s.key == "tech_news")
        assert page.lead.item.id == "hero"
        assert page.secondary.item.id == "t"
        assert papers.total == 1 and papers.lead is None
        assert tech.total == 1 and tech.lead is None


class TestDateLong:
    def test_vietnamese_weekday_and_dots(self):
        assert _format_date_long("2026-11-19") == "THỨ NĂM, 19.11.2026"

    def test_invalid_date_falls_back_to_raw(self):
        assert _format_date_long("not-a-date") == "not-a-date"
