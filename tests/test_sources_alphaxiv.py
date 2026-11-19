"""alphaXiv source against the schema verified live 2026-11-19:

get_hot_feed(limit) -> {"papers": [{"universal_paper_id": <bare arXiv id>}, ...]}
(app-ordered hot list, no metadata) — so the fetcher resolves titles/abstracts
with one batched arXiv id_list call.
"""

import json

import httpx
import pytest
import respx

from daily_digest.config import AlphaxivCfg, Config
from daily_digest.sources import REGISTRY, fetch_all
from daily_digest.sources.alphaxiv import (
    ALPHAXIV_MCP_URL,
    ARXIV_API_URL,
    AlphaxivError,
    fetch_alphaxiv,
    fetch_arxiv_metadata,
    hot_feed_ids,
)
from helpers import make_config, make_item

JSON_HEADERS = {"Content-Type": "application/json"}

HOT_FEED = {
    "papers": [
        {"universal_paper_id": "2611.23144"},
        {"universal_paper_id": "2611.21607"},
        {"universal_paper_id": "2611.21250"},
        {"universal_paper_id": "not-an-id"},  # junk -> skipped
        {"universal_paper_id": "2611.23144"},  # duplicate -> dedup
        {"arxiv_id": "2611.21919"},  # alternate key shape -> still parsed
    ]
}

ARXIV_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>ArXiv Query</title>
  <entry>
    <id>http://arxiv.org/abs/2611.23144v1</id>
    <title>  Hot Paper One: LLM Agents   with odd spacing </title>
    <summary> We study agents that  use tools reliably. </summary>
    <published>2026-11-18T00:00:00Z</published>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2611.21607v2</id>
    <title>Hot Paper Two: Reward Modeling</title>
    <summary>Scaling reward models.</summary>
    <published>2026-11-17T00:00:00Z</published>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2611.21919v1</id>
    <title>Hot Paper Three</title>
    <summary>Third paper.</summary>
    <published>2026-11-16T00:00:00Z</published>
  </entry>
</feed>
"""


def _tool_result(feed_payload) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {
            "content": [{"type": "text", "text": json.dumps(feed_payload)}],
            "isError": False,
        },
    }


def test_hot_feed_ids_ordered_and_deduped():
    ids = hot_feed_ids(_tool_result(HOT_FEED))
    assert ids == ["2611.23144", "2611.21607", "2611.21250", "2611.21919"]


def test_hot_feed_ids_unwraps_envelope_and_structured_content():
    ids = hot_feed_ids(_tool_result(HOT_FEED))  # full envelope unwrapped
    assert ids
    structured = {"result": {"structuredContent": {"papers": HOT_FEED["papers"][:2]}}}
    assert hot_feed_ids(structured) == ["2611.23144", "2611.21607"]


def test_fetch_arxiv_metadata_parses_atom():
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, text=ARXIV_ATOM)
        )
    ) as client:
        metadata = fetch_arxiv_metadata(
            client, ["2611.23144", "2611.21607", "2611.21919"]
        )
    assert set(metadata) == {"2611.23144", "2611.21607", "2611.21919"}
    assert (
        metadata["2611.23144"]["title"] == "Hot Paper One: LLM Agents with odd spacing"
    )
    assert (
        metadata["2611.23144"]["summary"] == "We study agents that use tools reliably."
    )
    assert metadata["2611.23144"]["published"] is not None


def _mock_mcp_and_arxiv(monkeypatch, feed_payload):
    monkeypatch.setenv("ALPHAXIV_API_KEY", "test-key")
    calls: list[dict] = []

    def mcp_handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        if body.get("method") == "initialize":
            return httpx.Response(
                200,
                headers={**JSON_HEADERS, "Mcp-Session-Id": "ses-mcp-1"},
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {"tools": {}},
                    },
                },
            )
        if body.get("method") == "notifications/initialized":
            return httpx.Response(202)
        assert body["params"]["name"] == "get_hot_feed"
        assert body["params"]["arguments"] == {
            "limit": 20
        }  # schema-verified: only `limit`
        return httpx.Response(
            200, headers=JSON_HEADERS, json=_tool_result(feed_payload)
        )

    respx.post(ALPHAXIV_MCP_URL).mock(side_effect=mcp_handler)
    respx.get(ARXIV_API_URL).respond(200, text=ARXIV_ATOM)
    return calls


@respx.mock
def test_fetch_alphaxiv_full_flow(monkeypatch):
    calls = _mock_mcp_and_arxiv(monkeypatch, HOT_FEED)
    with httpx.Client() as client:
        items = fetch_alphaxiv(client, AlphaxivCfg(enabled=True, max_items=20))

    assert [m["method"] for m in calls] == [
        "initialize",
        "notifications/initialized",
        "tools/call",
    ]
    # hot-feed ORDER preserved; metadata resolved from arXiv
    assert [i.id for i in items] == [
        "arxiv:2611.23144",
        "arxiv:2611.21607",
        "arxiv:2611.21919",  # 2611.21250 has no Atom entry -> skipped (link blog case)
    ]
    assert items[0].title == "Hot Paper One: LLM Agents with odd spacing"
    assert items[0].source == "alphaxiv"
    assert items[0].points is None  # the signal is membership + order, not counts
    assert items[0].published is not None
    assert items[0].url == "https://arxiv.org/abs/2611.23144"


@respx.mock
def test_fetch_alphaxiv_sse_response_variant(monkeypatch):
    monkeypatch.setenv("ALPHAXIV_API_KEY", "test-key")
    inner = json.dumps({"papers": HOT_FEED["papers"][:1]})
    sse_body = (
        "event: message\n"
        'data: {"jsonrpc":"2.0","id":2,"result":{"content":[{"type":"text","text":"'
        + inner.replace('"', '\\"')
        + '"}]}}\n\n'
    )

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body.get("method") == "initialize":
            return httpx.Response(
                200,
                headers=JSON_HEADERS,
                json={"jsonrpc": "2.0", "id": 1, "result": {}},
            )
        if body.get("method") == "notifications/initialized":
            return httpx.Response(202)
        return httpx.Response(
            200, headers={"Content-Type": "text/event-stream"}, text=sse_body
        )

    respx.post(ALPHAXIV_MCP_URL).mock(side_effect=handler)
    respx.get(ARXIV_API_URL).respond(200, text=ARXIV_ATOM)
    with httpx.Client() as client:
        items = fetch_alphaxiv(client, AlphaxivCfg(enabled=True))
    assert [i.id for i in items] == ["arxiv:2611.23144"]


def test_fetch_alphaxiv_skips_without_key():
    import os

    key = os.environ.pop("ALPHAXIV_API_KEY", None)
    try:
        with httpx.Client() as client:
            assert fetch_alphaxiv(client, AlphaxivCfg(enabled=True)) == []
    finally:
        if key:
            os.environ["ALPHAXIV_API_KEY"] = key


@respx.mock
def test_fetch_alphaxiv_bad_key_is_isolated_as_source_error(monkeypatch, tmp_path):
    monkeypatch.setenv("ALPHAXIV_API_KEY", "bad-key")
    respx.post(ALPHAXIV_MCP_URL).respond(
        401, json={"error": {"message": "Invalid Authorization"}}
    )

    config = make_config(tmp_path)
    for name in ("hn", "hf_papers", "arxiv", "emergent_mind"):
        getattr(config.sources, name).enabled = False

    with httpx.Client() as client:
        items, errors = fetch_all(client, config)
    assert items == []
    assert len(errors) == 1
    assert errors[0].source == "alphaxiv"


@respx.mock
def test_fetch_alphaxiv_empty_shape_raises_visible_error(monkeypatch):
    monkeypatch.setenv("ALPHAXIV_API_KEY", "test-key")
    cfg = AlphaxivCfg(enabled=True)

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body.get("method") == "initialize":
            return httpx.Response(
                200,
                headers=JSON_HEADERS,
                json={"jsonrpc": "2.0", "id": 1, "result": {}},
            )
        if body.get("method") == "notifications/initialized":
            return httpx.Response(202)
        return httpx.Response(
            200, headers=JSON_HEADERS, json=_tool_result({"unexpected": "shape"})
        )

    respx.post(ALPHAXIV_MCP_URL).mock(side_effect=handler)
    with httpx.Client() as client:
        with pytest.raises(AlphaxivError):
            fetch_alphaxiv(client, cfg)


@respx.mock
def test_fetch_alphaxiv_unresolvable_ids_raise(monkeypatch):
    monkeypatch.setenv("ALPHAXIV_API_KEY", "test-key")
    _mock_mcp_and_arxiv(monkeypatch, {"papers": [{"universal_paper_id": "2401.99999"}]})
    with httpx.Client() as client:
        with pytest.raises(AlphaxivError):
            fetch_alphaxiv(client, AlphaxivCfg(enabled=True))


def test_alphaxiv_registered_by_default():
    config = Config()
    assert "alphaxiv" in REGISTRY
    assert config.sources.alphaxiv.enabled is True
    assert config.sources.alphaxiv.api_key_env == "ALPHAXIV_API_KEY"
    assert config.sources.alphaxiv.max_items == 20


def test_alphaxiv_merge_priority_between_hf_and_em():
    from daily_digest.pipeline import merge_items

    base = dict(title="T", url="https://arxiv.org/abs/2611.9")
    hf = make_item(id="arxiv:2611.9", source="hf_papers", points=10, **base)
    ax = make_item(id="arxiv:2611.9", source="alphaxiv", points=99, **base)
    em = make_item(id="arxiv:2611.9", source="emergentmind", **base)

    assert merge_items([ax, hf])[0].source == "hf_papers"  # curation beats community
    assert (
        merge_items([em, ax])[0].source == "alphaxiv"
    )  # community hot beats raw trending
    merged = merge_items([hf, ax])
    assert merged[0].points == 99  # max points kept across provenance choice


def test_alphaxiv_why_line_and_citations(tmp_path):
    import dataclasses

    from daily_digest.ranking.heuristic import rank_heuristic, score_item

    config = make_config(tmp_path)
    ax = make_item(
        id="arxiv:2611.1",
        title="A paper about LLM reasoning",
        url="https://arxiv.org/abs/2611.1",
        source="alphaxiv",
        points=30,
    )
    ax_cited = dataclasses.replace(ax, citations=200)
    assert score_item(ax, config) < score_item(ax_cited, config)
    ranked = rank_heuristic([ax], config)
    assert ranked[0].section == "papers"
    assert "alphaXiv" in ranked[0].why
