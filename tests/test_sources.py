"""Source fetchers against recorded fixtures (respx) — no live calls."""

import json

import httpx
import respx

from daily_digest.config import ArxivCfg, HfPapersCfg, HnCfg
from daily_digest.sources import REGISTRY, SourceError, fetch_all
from daily_digest.sources.arxiv import ARXIV_RSS_URL, fetch_arxiv, parse_rss
from daily_digest.sources.emergent_mind import EMERGENT_MIND_RSS_URL
from daily_digest.sources.hf_papers import HF_DAILY_PAPERS_URL, fetch_hf_papers
from daily_digest.sources.hn import ALGOLIA_URL, fetch_hn
from helpers import FIXTURES, make_config, make_item


def _json(name: str):
    return json.loads(FIXTURES.joinpath(name).read_text(encoding="utf-8"))


@respx.mock
def test_fetch_hn_maps_fields_and_filters():
    respx.get(ALGOLIA_URL).respond(200, json=_json("hn_front_page.json"))
    with httpx.Client() as client:
        items = fetch_hn(client, HnCfg(enabled=True, min_points=30, hits=60))

    assert [i.id for i in items] == [
        "hn:1001",
        "hn:1002",
        "hn:1005",
    ]  # low score + no title dropped
    assert items[0].points == 420
    assert items[0].url == "https://example.com/llm-reasoning"
    assert (
        items[1].url == "https://news.ycombinator.com/item?id=1002"
    )  # url=null fallback
    assert "<" not in items[1].summary  # story_text HTML stripped
    assert items[0].published is not None


@respx.mock
def test_fetch_hf_papers_maps_fields():
    respx.get(HF_DAILY_PAPERS_URL).respond(200, json=_json("hf_daily_papers.json"))
    with httpx.Client() as client:
        items = fetch_hf_papers(client, HfPapersCfg(enabled=True, max_items=30))

    assert len(items) == 3  # broken entry skipped
    assert items[0].id == "arxiv:2611.21938"
    assert items[0].url == "https://arxiv.org/abs/2611.21938"
    assert items[0].points == 42
    assert items[0].source == "hf_papers"
    assert items[0].published is not None


@respx.mock
def test_fetch_hf_papers_falls_back_to_yesterday():
    fixture = _json("hf_daily_papers.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("date"):
            return httpx.Response(200, json=fixture)
        return httpx.Response(200, json=[])

    respx.get(HF_DAILY_PAPERS_URL).mock(side_effect=handler)
    with httpx.Client() as client:
        items = fetch_hf_papers(client, HfPapersCfg(enabled=True, max_items=30))
    assert len(items) == 3


def test_parse_rss_keeps_only_new_and_caps():
    xml = FIXTURES.joinpath("arxiv_cs_cl.xml").read_text(encoding="utf-8")
    items = parse_rss(xml, cap=40)
    assert [i.id for i in items] == [
        "arxiv:2611.11111",
        "arxiv:2611.11444",
        "arxiv:2611.11555",
    ]
    assert items[0].summary.startswith("We distill reasoning")
    assert items[0].url == "https://arxiv.org/abs/2611.11111"
    assert len(parse_rss(xml, cap=2)) == 2


@respx.mock
def test_fetch_arxiv_multiple_categories(tmp_path):
    xml = FIXTURES.joinpath("arxiv_cs_cl.xml").read_text(encoding="utf-8")
    respx.get(ARXIV_RSS_URL.format(category="cs.CL")).respond(200, text=xml)
    respx.get(ARXIV_RSS_URL.format(category="cs.LG")).respond(200, text=xml)
    cfg = ArxivCfg(
        enabled=True,
        categories=["cs.CL", "cs.LG"],
        max_per_category=40,
        pause_seconds=0.0,
    )
    with httpx.Client() as client:
        items = fetch_arxiv(client, cfg)
    assert len(items) == 6  # 3 per category


@respx.mock
def test_fetch_arxiv_filters_non_llm_noise_in_broad_categories():
    xml = """<?xml version='1.0' encoding='UTF-8'?>
    <rss xmlns:arxiv="http://arxiv.org/schemas/atom" version="2.0">
      <channel>
        <title>cs.CR updates on arXiv.org</title>
        <item>
          <title>A new block cipher for constrained devices</title>
          <link>https://arxiv.org/abs/2611.90001</link>
          <description>arXiv:2611.90001v1 Announce Type: new
Abstract: A lightweight cipher with no learning component.</description>
        </item>
        <item>
          <title>Prompt injection against LLM agents</title>
          <link>https://arxiv.org/abs/2611.90002</link>
          <description>arXiv:2611.90002v1 Announce Type: new
Abstract: We study prompt injection attacks on tool-using language model agents.</description>
        </item>
      </channel>
    </rss>"""
    respx.get(ARXIV_RSS_URL.format(category="cs.CR")).respond(200, text=xml)
    cfg = ArxivCfg(
        enabled=True,
        categories=["cs.CR"],
        max_per_category=30,
        pause_seconds=0.0,
        filter_categories=["cs.CR"],
        filter_topics=["LLM", "prompt injection", "agent"],
    )
    with httpx.Client() as client:
        items = fetch_arxiv(client, cfg)

    assert [item.id for item in items] == ["arxiv:2611.90002"]
    assert "Prompt injection" in items[0].title


@respx.mock
def test_fetch_all_isolates_source_failures(tmp_path):
    config = make_config(tmp_path)
    xml = FIXTURES.joinpath("arxiv_cs_cl.xml").read_text(encoding="utf-8")
    em_rss = FIXTURES.joinpath("emergent_mind_rss.xml").read_text(encoding="utf-8")
    respx.get(ALGOLIA_URL).respond(500)  # HN down
    respx.get(HF_DAILY_PAPERS_URL).respond(200, json=_json("hf_daily_papers.json"))
    for category in config.sources.arxiv.categories:
        respx.get(ARXIV_RSS_URL.format(category=category)).respond(200, text=xml)
    respx.get(EMERGENT_MIND_RSS_URL).respond(200, text=em_rss)

    with httpx.Client() as client:
        items, errors = fetch_all(client, config)

    assert [e.source for e in errors] == ["hn"]
    assert items, "healthy sources still delivered items"
    assert all(i.source != "hn" for i in items)


@respx.mock
def test_fetch_all_all_sources_fail(tmp_path):
    config = make_config(tmp_path)
    respx.get(ALGOLIA_URL).respond(500)
    respx.get(HF_DAILY_PAPERS_URL).respond(500)
    for category in config.sources.arxiv.categories:
        respx.get(ARXIV_RSS_URL.format(category=category)).respond(500)
    respx.get(EMERGENT_MIND_RSS_URL).respond(500)

    with httpx.Client() as client:
        items, errors = fetch_all(client, config)
    assert items == []
    assert {e.source for e in errors} == {"hn", "hf_papers", "arxiv", "emergent_mind"}
    assert all(isinstance(e, SourceError) for e in errors)


def test_registry_extension(tmp_path, monkeypatch):
    """The discriminating test: a new source plugs in without touching the pipeline."""
    config = make_config(tmp_path)
    for name in REGISTRY:  # disable every built-in source, whatever they are
        getattr(config.sources, name).enabled = False

    class SubCfg:
        enabled = True

    config.sources.stub = SubCfg()
    REGISTRY["stub"] = lambda client, cfg: [
        make_item(
            id="url:x", title="Stub item", url="https://example.com/stub", source="stub"
        )
    ]
    try:
        with httpx.Client() as client:
            items, errors = fetch_all(client, config)
    finally:
        del REGISTRY["stub"]
        del config.sources.stub

    assert errors == []
    assert [i.title for i in items] == ["Stub item"]
