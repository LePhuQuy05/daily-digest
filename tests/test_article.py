"""Article-page description helpers: parsing, hydration and SSRF guards."""

from __future__ import annotations

import httpx
import pytest
import respx

from daily_digest.article import (
    MIN_DESCRIPTION_CHARS,
    article_lead,
    hydrate_item,
    meta_description,
)
from daily_digest.model import Item
from daily_digest.net import assert_public_url
from helpers import make_item


def _thin_item(url: str = "https://story.example/post") -> Item:
    return make_item(
        id="hn:1",
        title="AI agents change audit work",
        url=url,
        source="hn",
        points=80,
        summary="",
    )


class TestParsers:
    def test_meta_description_picks_the_longest_useful_one(self):
        page = (
            "<html><head>"
            '<meta property="og:description" content="Short one.">'
            '<meta name="description" content="A much longer description that '
            'explains the whole story and should win the comparison.">'
            "</head></html>"
        )
        assert meta_description(page).startswith("A much longer description")

    def test_article_lead_skips_navigation_and_picks_the_intro(self):
        page = (
            "<html><body><main>"
            "<p>Search models, datasets, users... Ctrl K Models Datasets Spaces Docs</p>"
            "<p>Today we are releasing a new open model trained with reinforcement "
            "learning on long-horizon agent tasks. It uses a 256K context and ships "
            "with evaluation recipes for reproducibility.</p>"
            "</main></body></html>"
        )
        lead = article_lead(page)

        assert lead.startswith("Today we are releasing")
        assert "Search models" not in lead


class TestHydrateItem:
    @respx.mock
    def test_fills_thin_summary_from_meta_description(self, monkeypatch):
        monkeypatch.setattr("daily_digest.net.host_is_public", lambda host: True)
        description = (
            "A detailed agent API description that is long enough to use in the "
            "digest summary today."
        )
        respx.get("https://story.example/post").respond(
            200,
            text=f'<html><head><meta property="og:description" content="{description}"></head></html>',
        )
        with httpx.Client() as client:
            hydrated = hydrate_item(client, _thin_item())

        assert hydrated.summary == description
        assert hydrated.url == "https://story.example/post"

    @respx.mock
    def test_http_error_keeps_item_unchanged(self, monkeypatch):
        monkeypatch.setattr("daily_digest.net.host_is_public", lambda host: True)
        respx.get("https://story.example/post").respond(500)
        item = _thin_item()
        with httpx.Client() as client:
            hydrated = hydrate_item(client, item)

        assert hydrated is item
        assert hydrated.summary == ""

    @respx.mock
    def test_oversized_page_keeps_item_unchanged(self, monkeypatch):
        monkeypatch.setattr("daily_digest.net.host_is_public", lambda host: True)
        respx.get("https://story.example/post").respond(200, content=b"x" * 64)
        item = _thin_item()
        with httpx.Client() as client:
            hydrated = hydrate_item(client, item, max_bytes=10)

        assert hydrated is item

    @respx.mock
    def test_short_description_keeps_item_unchanged(self, monkeypatch):
        monkeypatch.setattr("daily_digest.net.host_is_public", lambda host: True)
        respx.get("https://story.example/post").respond(
            200,
            text='<html><head><meta property="og:description" content="too short">'
            "</head><body><p>also too short</p></body></html>",
        )
        item = _thin_item()
        with httpx.Client() as client:
            hydrated = hydrate_item(client, item)

        assert hydrated is item

    def test_item_with_real_summary_is_not_fetched(self):
        item = make_item(
            id="hn:2",
            title="Already described",
            url="https://story.example/done",
            source="hn",
            summary="x" * MIN_DESCRIPTION_CHARS,
        )

        def boom(request: httpx.Request) -> httpx.Response:
            raise AssertionError("network call")

        with httpx.Client(transport=httpx.MockTransport(boom)) as client:
            assert hydrate_item(client, item) is item


class TestSsrf:
    def test_private_and_non_http_urls_are_blocked(self):
        for url in (
            "http://127.0.0.1/a",
            "http://localhost/a",
            "http://machine.local/a",
            "file:///a",
        ):
            with pytest.raises(ValueError):
                assert_public_url(url)

    def test_public_host_allowed_when_dns_is_public(self, monkeypatch):
        monkeypatch.setattr("daily_digest.net.host_is_public", lambda host: True)
        assert_public_url("https://example.com/a") is None
