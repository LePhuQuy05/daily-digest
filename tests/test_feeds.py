"""Curated feed source: RSS/Atom parsing, filters, isolation and config."""

from __future__ import annotations

import httpx
import pytest
import respx
import yaml

from daily_digest.config import ConfigError, FeedEntry, FeedsCfg, load_config
from daily_digest.source_labels import labels_for
from daily_digest.sources.feeds import _article_lead, fetch_feeds, parse_feed
from helpers import FIXTURES


def _rss() -> str:
    return FIXTURES.joinpath("tech_rss.xml").read_text(encoding="utf-8")


def _atom() -> str:
    return FIXTURES.joinpath("tech_atom.xml").read_text(encoding="utf-8")


def _releases() -> str:
    return FIXTURES.joinpath("github_releases.atom").read_text(encoding="utf-8")


def test_parse_rss_maps_fields_cleans_html_and_caps():
    entry = FeedEntry(
        "openai_news",
        "https://example.test/rss",
        "OpenAI",
        max_items=2,
        max_age_days=0,
    )
    items = parse_feed(_rss(), entry, [])

    assert len(items) == 2  # cap applied; oldest item would be third
    first = items[0]
    assert first.title == "OpenAI ships an agents API"
    assert first.url == "https://openai.example/agents-api"  # empty <link> -> guid
    assert first.source == "openai_news"
    assert first.section_hint == "tech_news"
    assert first.published is not None and first.published.tzinfo is not None
    assert first.summary == "A new LLM agent API with tool use and tracing."
    assert not first.id.startswith("http")
    assert first.id.startswith("feed:")


def test_parse_atom_uses_href_and_topic_filter():
    entry = FeedEntry(
        "the_verge_ai",
        "https://example.test/atom",
        "The Verge",
        max_items=10,
        max_age_days=0,
        require_topic=True,
    )
    items = parse_feed(_atom(), entry, ["AI", "GPU"])

    assert [item.title for item in items] == [
        "The Verge AI story",
        "New inference benchmark",
    ]
    assert items[0].url == "https://theverge.example/ai-story"
    assert items[0].summary == "An AI agent changes how teams ship software."
    assert items[1].url == "https://theverge.example/inference"


def test_parse_filters_items_older_than_max_age():
    entry = FeedEntry(
        "old_feed", "https://example.test/rss", max_age_days=30, max_items=10
    )
    # The fixture's 2024 item is far outside a 30-day window; the 2026 items
    # would be too if the test suite runs much later, so make the window tiny
    # and assert only that the old item is gone.
    items = parse_feed(_rss(), entry, [])
    assert all(item.title != "Old model card" for item in items)


def test_article_lead_skips_navigation_and_picks_the_intro():
    page = (
        "<html><body><main>"
        "<p>Search models, datasets, users... Ctrl K Models Datasets Spaces Docs</p>"
        "<p>Today we are releasing a new open model trained with reinforcement "
        "learning on long-horizon agent tasks. It uses a 256K context and ships "
        "with evaluation recipes for reproducibility.</p>"
        "</main></body></html>"
    )
    lead = _article_lead(page)

    assert lead.startswith("Today we are releasing")
    assert "Search models" not in lead


def test_parse_short_summary_falls_back_to_categories():
    xml = """<rss version="2.0"><channel><item>
      <title>Machine intelligence for science</title>
      <link>https://example.test/science</link>
      <description>Research</description>
      <category>Machine Intelligence</category>
      <category>Natural Language Processing</category>
      <pubDate>Wed, 18 Nov 2026 10:00:00 GMT</pubDate>
    </item></channel></rss>"""
    entry = FeedEntry("lab", "https://example.test/rss", max_age_days=0)
    items = parse_feed(xml, entry, [])

    assert "Machine Intelligence" in items[0].summary
    assert "Natural Language Processing" in items[0].summary


def test_parse_tools_skips_prereleases_and_sets_section_hint():
    entry = FeedEntry(
        "gh_vllm",
        "https://example.test/releases",
        "vLLM",
        section="tools_releases",
        max_items=10,
        max_age_days=0,
    )
    items = parse_feed(_releases(), entry, [])

    assert [item.title for item in items] == ["v0.34.0", "v0.33.0"]
    assert all(item.section_hint == "tools_releases" for item in items)
    assert "Stable release" in items[0].summary


@respx.mock
def test_fetch_feeds_hydrates_a_thin_summary_from_meta_description():
    respx.get("https://lab.example/rss").respond(200, text=_rss())
    respx.get("https://openai.example/agents-api").respond(
        200,
        text=(
            '<html><head><meta property="og:description" '
            'content="A detailed agent API description that is long enough to use in the digest summary today.">'
            "</head></html>"
        ),
    )
    cfg = FeedsCfg(
        entries=[
            FeedEntry(
                "lab_feed",
                "https://lab.example/rss",
                max_items=1,
                max_age_days=0,
                hydrate=True,
            )
        ]
    )
    with httpx.Client() as client:
        items = fetch_feeds(client, cfg)

    assert items[0].summary == (
        "A detailed agent API description that is long enough to use in the digest summary today."
    )


@respx.mock
def test_fetch_feeds_isolates_a_failing_feed():
    respx.get("https://bad.example/rss").respond(500)
    respx.get("https://good.example/rss").respond(200, text=_rss())
    cfg = FeedsCfg(
        entries=[
            FeedEntry("bad_feed", "https://bad.example/rss", max_age_days=0),
            FeedEntry("good_feed", "https://good.example/rss", max_age_days=0),
        ]
    )
    with httpx.Client() as client:
        items = fetch_feeds(client, cfg)

    assert items and all(item.source == "good_feed" for item in items)


@respx.mock
def test_fetch_feeds_raises_only_when_every_feed_fails():
    respx.get("https://bad.example/rss").respond(500)
    cfg = FeedsCfg(
        entries=[FeedEntry("bad_feed", "https://bad.example/rss", max_age_days=0)]
    )
    with httpx.Client() as client:
        with pytest.raises(ValueError):
            fetch_feeds(client, cfg)


def test_default_feed_list_is_enabled_and_curated(tmp_path):
    config = load_config(tmp_path / "missing.yaml")
    names = {entry.name for entry in config.sources.feeds.entries}

    assert config.sources.feeds.enabled is True
    assert len(config.sources.feeds.entries) >= 20
    assert {"openai_news", "the_verge_ai", "gh_vllm"} <= names
    assert all(
        entry.url.startswith("https://") for entry in config.sources.feeds.entries
    )


def test_yaml_can_override_the_feed_list(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "sources": {
                    "feeds": {
                        "entries": [
                            {
                                "name": "custom_feed",
                                "url": "https://example.test/feed",
                                "label": "Custom",
                                "section": "tools_releases",
                                "max_items": 1,
                            }
                        ]
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    config = load_config(path)

    assert len(config.sources.feeds.entries) == 1
    entry = config.sources.feeds.entries[0]
    assert entry.name == "custom_feed"
    assert entry.label == "Custom"
    assert entry.section == "tools_releases"
    assert entry.max_items == 1


def test_custom_feed_label_is_used_for_the_ui(tmp_path):
    config = load_config(tmp_path / "missing.yaml")
    config.sources.feeds.entries = [
        FeedEntry(
            "custom_feed",
            "https://example.test/feed",
            "Custom Publication",
        )
    ]
    labels = labels_for(config)

    assert labels["custom_feed"] == "Custom Publication"
    assert labels["hn"] == "Hacker News"


def test_invalid_feed_config_is_rejected(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        "sources:\n  feeds:\n    entries:\n      - name: bad\n        url: file:///etc/passwd\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_config(path)


def test_feeds_must_be_a_mapping(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("sources:\n  feeds: false\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(path)


def test_duplicate_feed_names_are_rejected(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        "sources:\n  feeds:\n    entries:\n"
        "      - {name: same, url: 'https://a.example/rss'}\n"
        "      - {name: same, url: 'https://b.example/rss'}\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_config(path)
