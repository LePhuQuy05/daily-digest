# ------------------------------------------------------------------ Emergent Mind


"""Emergent Mind source: parse/filter tests, HTTP test, registry + merge priority."""

import httpx
import respx

from daily_digest.config import EmergentMindCfg
from daily_digest.sources import REGISTRY
from daily_digest.sources.emergent_mind import (
    EMERGENT_MIND_RSS_URL,
    fetch_emergent_mind,
    parse_emergent_mind_rss,
)
from helpers import FIXTURES, make_config, make_item


def _em_rss() -> str:
    return FIXTURES.joinpath("emergent_mind_rss.xml").read_text(encoding="utf-8")


def test_parse_emergent_mind_filters_and_extracts():
    cfg = EmergentMindCfg(enabled=True, max_items=20, require_topic=True)
    items = parse_emergent_mind_rss(_em_rss(), cfg)

    # AI items kept; physics/number-theory noise and the non-arXiv entry dropped;
    # the duplicate feed entry collapsed to one item.
    assert [i.id for i in items] == ["arxiv:2611.14996", "arxiv:2611.11112"]
    assert (
        items[0].url == "https://arxiv.org/abs/2611.14996"
    )  # canonical URL, not the search link
    assert items[0].source == "emergentmind"
    assert items[0].points is None
    assert items[0].published is not None
    # abstract extracted, HTML stripped, arXiv marker removed
    assert items[0].summary.startswith("Humans often cheat")
    assert "<" not in items[0].summary
    assert "arxiv" not in items[0].summary.lower()
    # version suffix stripped from the id
    assert items[1].id == "arxiv:2611.11112"


def test_parse_emergent_mind_topic_filter_disabled():
    cfg = EmergentMindCfg(enabled=True, max_items=20, require_topic=False)
    items = parse_emergent_mind_rss(_em_rss(), cfg)
    assert (
        len(items) == 4
    )  # physics + number theory kept too; no-link entry still skipped


def test_parse_emergent_mind_caps_items():
    cfg = EmergentMindCfg(enabled=True, max_items=1, require_topic=False)
    assert len(parse_emergent_mind_rss(_em_rss(), cfg)) == 1


@respx.mock
def test_fetch_emergent_mind_via_http():
    respx.get(EMERGENT_MIND_RSS_URL).respond(200, text=_em_rss())
    with httpx.Client() as client:
        items = fetch_emergent_mind(client, EmergentMindCfg(enabled=True))
    assert len(items) == 2
    assert all(i.source == "emergentmind" for i in items)


def test_emergent_mind_is_registered_and_enabled_by_default(tmp_path):
    config = make_config(tmp_path)
    assert "emergent_mind" in REGISTRY
    assert "emergent_mind" in [
        name
        for name, fetcher in REGISTRY.items()
        if getattr(getattr(config.sources, name, None), "enabled", False)
    ]


def test_merge_prefers_emergent_mind_over_plain_arxiv():
    """Provenance priority: hf_papers > emergentmind > arxiv, regardless of arrival order."""
    from daily_digest.pipeline import merge_items

    arxiv_item = make_item(
        id="arxiv:2611.14996",
        title="T",
        url="https://arxiv.org/abs/2611.14996",
        source="arxiv",
    )
    em_item = make_item(
        id="arxiv:2611.14996",
        title="T",
        url="https://arxiv.org/abs/2611.14996",
        source="emergentmind",
    )
    hf_item = make_item(
        id="arxiv:2611.14996",
        title="T",
        url="https://arxiv.org/abs/2611.14996",
        source="hf_papers",
        points=15,
    )

    merged = merge_items([arxiv_item, em_item])
    assert len(merged) == 1 and merged[0].source == "emergentmind"
    merged = merge_items([em_item, arxiv_item])  # order must not matter
    assert merged[0].source == "emergentmind"
    merged = merge_items([em_item, hf_item])  # HF upvotes still win
    assert merged[0].source == "hf_papers" and merged[0].points == 15


def test_heuristic_gives_trending_sources_their_bonuses(tmp_path):
    """EM trending outranks an identical plain-arXiv item; HF trending outranks both."""
    from daily_digest.ranking.heuristic import score_item

    config = make_config(tmp_path)
    base = dict(title="A paper about LLM reasoning", url="https://arxiv.org/abs/2611.9", summary="")
    plain = make_item(id="arxiv:2611.9", source="arxiv", **base)
    em = make_item(id="arxiv:2611.9", source="emergentmind", **base)
    hf = make_item(id="arxiv:2611.9", source="hf_papers", points=5, **base)

    assert score_item(plain, config) < score_item(em, config)
    assert score_item(em, config) < score_item(hf, config)


def test_emergent_mind_why_line_and_section(tmp_path):
    from daily_digest.ranking.heuristic import rank_heuristic

    config = make_config(tmp_path)
    em = make_item(
        id="arxiv:2611.14996",
        title="Reward hacking pressure states in LLMs",
        url="https://arxiv.org/abs/2611.14996",
        source="emergentmind",
    )
    ranked = rank_heuristic([em], config)
    assert ranked[0].section == "papers"
    assert "Emergent Mind" in ranked[0].why
