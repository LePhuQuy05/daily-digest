"""OpenAlex citation enrichment: mapping, batch request shape, failure softness."""

import httpx
import respx

from daily_digest.enrich import (
    OPENALEX_WORKS_URL,
    _citations_by_arxiv_id,
    enrich_citations,
)
from helpers import make_config, make_item


def _works_response():
    """Mirrors the live 2026-11-19 probe: one arXiv-DOI work, one published-version work."""
    return {
        "results": [
            {
                "ids": {
                    "openalex": "https://openalex.org/W1",
                    "doi": "https://doi.org/10.48550/arxiv.2611.14996",
                },
                "cited_by_count": 0,
            },
            {
                "ids": {
                    "openalex": "https://openalex.org/W2",
                    "doi": "https://doi.org/10.1051/0004-6361/202450163",
                },
                "cited_by_count": 6,
                "locations": [
                    {"landing_page_url": "http://arxiv.org/abs/2407.21583"},
                    {"landing_page_url": "https://doi.org/10.1051/0004-6361/202450163"},
                ],
            },
        ],
        "meta": {"count": 2},
    }


def test_citations_mapping_doi_and_locations():
    mapping = _citations_by_arxiv_id(_works_response()["results"])
    assert mapping == {"2611.14996": 0, "2407.21583": 6}


def test_citations_mapping_ignores_malformed_entries():
    assert (
        _citations_by_arxiv_id(
            [{"ids": {}}, "junk", {"ids": {"doi": None}, "cited_by_count": "x"}]
        )
        == {}
    )


@respx.mock
def test_enrich_citations_batches_doi_filter_and_sets_counts(tmp_path):
    config = make_config(tmp_path)
    config.enrichment.enabled = True
    config.enrichment.email = "me@example.com"

    route = respx.get(OPENALEX_WORKS_URL).respond(200, json=_works_response())
    items = [
        make_item(
            id="arxiv:2611.14996",
            title="A",
            url="https://arxiv.org/abs/2611.14996",
            source="arxiv",
        ),
        make_item(
            id="arxiv:2407.21583",
            title="B",
            url="https://arxiv.org/abs/2407.21583",
            source="emergentmind",
        ),
        make_item(
            id="hn:1", title="C", url="https://example.com/news", source="hn"
        ),  # not a paper
    ]

    enriched = enrich_citations(items, config)

    # request shape: batched DOI filter + select + per-page + polite-pool mailto
    from urllib.parse import unquote

    url = unquote(str(route.calls.last.request.url))
    assert "filter=doi:https://doi.org/10.48550/arxiv.2611.14996" in url
    assert "|https://doi.org/10.48550/arxiv.2407.21583" in url  # OR-joined batch
    assert "cited_by_count" in url
    assert "mailto=me@example.com" in url

    assert enriched[0].citations == 0
    assert enriched[1].citations == 6
    assert enriched[2].citations is None  # non-paper untouched


@respx.mock
def test_enrich_citations_failure_returns_items_unchanged(tmp_path):
    config = make_config(tmp_path)
    config.enrichment.enabled = True
    respx.get(OPENALEX_WORKS_URL).respond(500)
    items = [
        make_item(
            id="arxiv:2611.1",
            title="A",
            url="https://arxiv.org/abs/2611.1",
            source="arxiv",
        )
    ]
    assert enrich_citations(items, config) == items


@respx.mock
def test_enrich_citations_skips_when_disabled(tmp_path):
    config = make_config(tmp_path)
    config.enrichment.enabled = False
    items = [
        make_item(
            id="arxiv:2611.1",
            title="A",
            url="https://arxiv.org/abs/2611.1",
            source="arxiv",
        )
    ]
    respx.get(OPENALEX_WORKS_URL)  # would fail if called
    assert enrich_citations(items, config) == items


def test_enrich_citations_no_arxiv_items_is_noop(tmp_path):
    config = make_config(tmp_path)
    items = [make_item(id="hn:1", title="A", url="https://example.com/x", source="hn")]
    assert enrich_citations(items, config) == items


def test_pipeline_calls_enrichment_on_pool(tmp_path, monkeypatch):
    """The pool passes through enrich_citations (guarded by conftest's autouse fixture)."""
    import daily_digest.pipeline as pipeline
    from daily_digest.pipeline import run_day
    from helpers import FakeLlmClient, llm_ok_json

    calls: list = []

    def fake_enrich(items, config):
        calls.append(len(items))
        return items

    monkeypatch.setattr(pipeline, "enrich_citations", fake_enrich)
    config = make_config(tmp_path)
    fetch_items = [
        make_item(
            id=f"arxiv:2611.0000{i}",
            title=f"LLM paper {i}",
            url=f"https://arxiv.org/abs/2611.0000{i}",
            source="arxiv",
        )
        for i in range(4)
    ]
    monkeypatch.setattr(
        pipeline,
        "fetch_all",
        lambda client, cfg: (fetch_items, []),
    )
    result = run_day(
        config,
        "2026-11-18",
        llm_client=FakeLlmClient(llm_ok_json(8)),
        notify_fn=lambda *a, **k: None,
    )
    assert result.exit_code == 0
    assert calls == [4]  # enrichment ran once over the whole pool


def test_editor_candidate_line_includes_citations(tmp_path):
    from daily_digest.ranking.llm import _candidate_line

    plain = make_item(
        id="arxiv:2611.1", title="T", url="https://arxiv.org/abs/2611.1", source="arxiv"
    )
    cited = make_item(
        id="arxiv:2611.1",
        title="T",
        url="https://arxiv.org/abs/2611.1",
        source="arxiv",
        points=12,
        summary="an abstract",
    )
    import dataclasses

    cited = dataclasses.replace(cited, citations=40)
    assert "40 citations" in _candidate_line(0, cited)
    assert "12 pts" in _candidate_line(0, cited)
    assert "citations" not in _candidate_line(0, plain)
