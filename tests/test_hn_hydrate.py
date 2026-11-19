"""HN link-post hydration: candidate selection, bounds, and pipeline wiring."""

from __future__ import annotations

import httpx
import respx

import daily_digest.pipeline as pipeline
from daily_digest.article import hydrate_hn_links
from daily_digest.pipeline import run_day
from helpers import FakeLlmClient, llm_ok_json, make_config, make_item


DESCRIPTION = (
    "AI agents asked better questions than accountants in a controlled audit "
    "trial, with details long enough to count as a real summary."
)


def _hn(
    uid: str = "hn:1",
    url: str = "https://audit.example/trial",
    title: str = "AI agents ask better questions in audit trial",
    points: int | None = 80,
):
    return make_item(
        id=uid, title=title, url=url, source="hn", points=points, summary=""
    )


def _no_fetch_client() -> httpx.Client:
    def boom(request: httpx.Request) -> httpx.Response:
        raise AssertionError("network call")

    return httpx.Client(transport=httpx.MockTransport(boom))


def _page(description: str = DESCRIPTION) -> str:
    return (
        '<html><head><meta property="og:description" '
        f'content="{description}"></head></html>'
    )


@respx.mock
def test_link_post_gets_meta_description(tmp_path, monkeypatch):
    monkeypatch.setattr("daily_digest.net.host_is_public", lambda host: True)
    respx.get("https://audit.example/trial").respond(200, text=_page())
    config = make_config(tmp_path)
    items = [_hn()]

    with httpx.Client() as client:
        out = hydrate_hn_links(items, config, client)

    assert out[0].summary == DESCRIPTION
    assert out is not items
    assert items[0].summary == ""  # input list untouched (frozen Item replaced)


def test_self_post_is_not_fetched(tmp_path):
    config = make_config(tmp_path)
    items = [
        _hn(
            url="https://news.ycombinator.com/item?id=50547777",
            title="Ask HN: AI tooling",
        )
    ]
    out = hydrate_hn_links(items, config, _no_fetch_client())
    assert out[0].summary == ""


def test_off_topic_link_is_not_fetched(tmp_path):
    config = make_config(tmp_path)
    items = [
        _hn(url="https://city.example/budget", title="City council budget hearing")
    ]
    out = hydrate_hn_links(items, config, _no_fetch_client())
    assert out[0].summary == ""


@respx.mock
def test_limit_fetches_highest_points_first(tmp_path, monkeypatch):
    monkeypatch.setattr("daily_digest.net.host_is_public", lambda host: True)
    high = respx.get("https://audit.example/high").respond(200, text=_page())
    low = respx.get("https://audit.example/low").respond(500)
    config = make_config(tmp_path)
    config.sources.hn.hydrate_limit = 1
    items = [
        _hn("hn:low", "https://audit.example/low", points=10),
        _hn("hn:high", "https://audit.example/high", points=200),
    ]

    with httpx.Client() as client:
        out = hydrate_hn_links(items, config, client)

    assert high.called and not low.called
    by_id = {item.id: item for item in out}
    assert by_id["hn:high"].summary == DESCRIPTION
    assert by_id["hn:low"].summary == ""


@respx.mock
def test_failed_page_keeps_item_and_never_raises(tmp_path, monkeypatch):
    monkeypatch.setattr("daily_digest.net.host_is_public", lambda host: True)
    respx.get("https://audit.example/trial").respond(500)
    config = make_config(tmp_path)
    items = [_hn()]

    with httpx.Client() as client:
        out = hydrate_hn_links(items, config, client)

    assert out[0].summary == ""


def test_hydrate_disabled_never_fetches(tmp_path):
    config = make_config(tmp_path)
    config.sources.hn.hydrate = False
    items = [_hn()]
    out = hydrate_hn_links(items, config, _no_fetch_client())
    assert out == items


@respx.mock
def test_run_day_hydrates_before_balanced_pool(tmp_path, monkeypatch):
    monkeypatch.setattr("daily_digest.net.host_is_public", lambda host: True)
    respx.get("https://audit.example/trial").respond(200, text=_page())
    config = make_config(tmp_path)
    items = [
        _hn(),
        make_item(
            id="arxiv:2611.11111",
            title="arXiv paper on RLHF",
            url="https://arxiv.org/abs/2611.11111",
            source="arxiv",
        ),
        make_item(
            id="arxiv:2611.22222",
            title="Interpretability study",
            url="https://arxiv.org/abs/2611.22222",
            source="arxiv",
        ),
    ]
    monkeypatch.setattr(pipeline, "fetch_all", lambda client, cfg: (items, []))

    captured: dict[str, list] = {}
    real_balanced = pipeline.balanced_pool

    def spy(pool_items, cfg, cap, adjustments=None):
        captured["pool"] = list(pool_items)
        return real_balanced(pool_items, cfg, cap, adjustments)

    monkeypatch.setattr(pipeline, "balanced_pool", spy)

    result = run_day(
        config,
        "2026-11-18",
        llm_client=FakeLlmClient(llm_ok_json(8)),
        notify_fn=lambda *a, **k: None,
    )

    assert result.exit_code == 0
    pool_hn = next(item for item in captured["pool"] if item.source == "hn")
    assert pool_hn.summary == DESCRIPTION
