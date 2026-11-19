"""Tech News source-diversity guard: one item per source, never padded."""

from __future__ import annotations

from daily_digest.model import RankedItem
from daily_digest.ranking import select
from daily_digest.ranking.diversify import diversify_tech_news
from helpers import FakeLlmClient, make_config, make_item


def _item(uid: str, source: str, summary: str = "x" * 100):
    return make_item(
        id=uid,
        title=f"Title {uid}",
        url=f"https://example.test/{uid}",
        source=source,
        summary=summary,
    )


def _ranked(item, section: str, why: str = "why") -> RankedItem:
    return RankedItem(item=item, why=why, section=section)


def _pool_with_duplicate():
    hf1 = _item("hf:1", "huggingface_blog")
    hf2 = _item("hf:2", "huggingface_blog")
    deepmind = _item("dm:1", "deepmind_blog")
    paper = _item("arxiv:1", "arxiv")
    ranked = [
        _ranked(paper, "papers"),
        _ranked(hf1, "tech_news"),
        _ranked(hf2, "tech_news"),
        _ranked(_item("arxiv:2", "arxiv"), "papers"),
    ]
    pool = [paper, hf1, hf2, deepmind, _item("arxiv:2", "arxiv")]
    return ranked, pool, hf1, hf2, deepmind


def test_replaces_duplicate_with_qualified_candidate(tmp_path):
    config = make_config(tmp_path)
    ranked, pool, hf1, hf2, deepmind = _pool_with_duplicate()

    result = diversify_tech_news(ranked, pool, config)

    assert [r.item for r in result] == [
        ranked[0].item,
        hf1,  # first (more important) pick stays
        deepmind,  # duplicate replaced at its own position
        ranked[3].item,
    ]
    assert result[2].section == "tech_news"
    assert result[2].why  # heuristic why-line, never empty


def test_no_unused_candidate_keeps_duplicate(tmp_path):
    config = make_config(tmp_path)
    ranked, pool, *_ = _pool_with_duplicate()
    pool = [item for item in pool if item.id != "dm:1"]  # nothing unused

    result = diversify_tech_news(ranked, pool, config)

    assert [r.item.source for r in result] == [
        "arxiv",
        "huggingface_blog",
        "huggingface_blog",
        "arxiv",
    ]


def test_thin_candidate_is_never_used_as_padding(tmp_path):
    config = make_config(tmp_path)
    ranked, pool, *_ = _pool_with_duplicate()
    for item in pool:
        if item.id == "dm:1":
            pool[pool.index(item)] = _item("dm:1", "deepmind_blog", summary="thin")

    result = diversify_tech_news(ranked, pool, config)

    assert result[2].item.id == "hf:2"  # duplicate kept, no padding


def test_candidate_from_an_already_present_source_is_skipped(tmp_path):
    config = make_config(tmp_path)
    ranked, pool, *_ = _pool_with_duplicate()
    # Only unused candidate shares a source with the duplicate -> blocked.
    pool = [item for item in pool if item.id not in {"dm:1"}]
    pool.append(_item("hf:3", "huggingface_blog"))

    result = diversify_tech_news(ranked, pool, config)

    assert result[2].item.id == "hf:2"


def test_select_applies_guard_on_llm_branch_before_top_n(tmp_path):
    config = make_config(tmp_path)
    paper = _item("arxiv:1", "arxiv")
    hf1 = _item("hf:1", "huggingface_blog")
    hf2 = _item("hf:2", "huggingface_blog")
    deepmind = _item("dm:1", "deepmind_blog")
    pool = [paper, hf1, hf2, deepmind]
    response = (
        '{"selected": ['
        '{"id": 1, "why": "w1", "section": "tech_news"},'
        '{"id": 2, "why": "w2", "section": "tech_news"},'
        '{"id": 0, "why": "w0", "section": "papers"}'
        "]}"
    )

    ranked, mode = select(pool, FakeLlmClient(response), config)

    assert mode == "llm"
    tech_sources = [r.item.source for r in ranked if r.section == "tech_news"]
    assert tech_sources == ["huggingface_blog", "deepmind_blog"]
    assert len({r.item.id for r in ranked}) == len(ranked)  # no duplicate uid


def test_select_guard_can_be_disabled(tmp_path):
    config = make_config(tmp_path)
    config.llm.diversify_tech_news = False
    paper = _item("arxiv:1", "arxiv")
    hf1 = _item("hf:1", "huggingface_blog")
    hf2 = _item("hf:2", "huggingface_blog")
    deepmind = _item("dm:1", "deepmind_blog")
    pool = [paper, hf1, hf2, deepmind]
    response = (
        '{"selected": ['
        '{"id": 1, "why": "w1", "section": "tech_news"},'
        '{"id": 2, "why": "w2", "section": "tech_news"},'
        '{"id": 0, "why": "w0", "section": "papers"}'
        "]}"
    )

    ranked, mode = select(pool, FakeLlmClient(response), config)

    assert mode == "llm"
    tech_sources = [r.item.source for r in ranked if r.section == "tech_news"]
    assert tech_sources == ["huggingface_blog", "huggingface_blog"]


def test_select_applies_guard_on_heuristic_branch(tmp_path):
    config = make_config(tmp_path)
    # Two same-source tech items with strong topic hits; one qualified other-source
    # candidate exists. The heuristic branch must also end with distinct sources.
    hf1 = make_item(
        id="hf:1",
        title="LLM agent benchmark news one",
        url="https://example.test/1",
        source="huggingface_blog",
        points=200,
        summary="x" * 100,
    )
    hf2 = make_item(
        id="hf:2",
        title="LLM agent benchmark news two",
        url="https://example.test/2",
        source="huggingface_blog",
        points=150,
        summary="x" * 100,
    )
    deepmind = make_item(
        id="dm:1",
        title="LLM agent benchmark news three",
        url="https://example.test/3",
        source="deepmind_blog",
        summary="x" * 100,
    )
    ieee = make_item(
        id="ieee:1",
        title="LLM agent benchmark news four",
        url="https://example.test/4",
        source="ieee_spectrum_ai",
        summary="x" * 100,
    )
    paper = make_item(
        id="arxiv:1",
        title="Paper",
        url="https://arxiv.org/abs/2611.1",
        source="arxiv",
    )
    config.llm.top_n = 3  # pool (5) > top_n, so a replacement candidate exists

    ranked, mode = select([hf1, hf2, deepmind, ieee, paper], None, config)

    assert mode == "heuristic"
    tech_sources = [r.item.source for r in ranked if r.section == "tech_news"]
    assert len(ranked) == config.llm.top_n
    assert sorted(tech_sources) == [
        "deepmind_blog",
        "huggingface_blog",
        "ieee_spectrum_ai",
    ]
    assert tech_sources.count("huggingface_blog") == 1
