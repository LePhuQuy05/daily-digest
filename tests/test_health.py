"""Per-feed health drill-down for the curated feed source."""

from __future__ import annotations

import argparse

import httpx
import respx

from daily_digest.cli import cmd_health
from daily_digest.config import FeedEntry, FeedsCfg
from daily_digest.sources.feeds import check_feeds
from helpers import FIXTURES, make_config


def _rss() -> str:
    return FIXTURES.joinpath("tech_rss.xml").read_text(encoding="utf-8")


def _cfg(*entries: FeedEntry) -> FeedsCfg:
    return FeedsCfg(entries=list(entries))


@respx.mock
def test_check_feeds_reports_ok_and_failure():
    respx.get("https://good.example/rss").respond(200, text=_rss())
    respx.get("https://bad.example/rss").respond(500)
    cfg = _cfg(
        FeedEntry("good_feed", "https://good.example/rss", max_age_days=0),
        FeedEntry("bad_feed", "https://bad.example/rss", max_age_days=0),
    )

    with httpx.Client() as client:
        health = check_feeds(client, cfg)

    assert [(feed.name, feed.ok, feed.item_count) for feed in health] == [
        ("good_feed", True, 3),
        ("bad_feed", False, 0),
    ]
    assert "HTTPStatusError" in health[1].error


@respx.mock
def test_check_feeds_marks_malformed_xml_as_failed():
    respx.get("https://broken.example/rss").respond(200, text="not-xml-at-all")
    cfg = _cfg(FeedEntry("broken_feed", "https://broken.example/rss", max_age_days=0))

    with httpx.Client() as client:
        health = check_feeds(client, cfg)

    assert health[0].ok is False
    assert "ParseError" in health[0].error


@respx.mock
def test_check_feeds_never_hydrates_article_pages(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("hydrate call")

    monkeypatch.setattr("daily_digest.sources.feeds.hydrate_item", boom)
    respx.get("https://lab.example/rss").respond(200, text=_rss())
    cfg = _cfg(
        FeedEntry("lab_feed", "https://lab.example/rss", max_age_days=0, hydrate=True)
    )

    with httpx.Client() as client:
        health = check_feeds(client, cfg)

    assert health[0].ok is True  # parse-only: no article fetch, no raise


@respx.mock
def test_cmd_health_prints_table_and_exits_zero(tmp_path, capsys):
    respx.get("https://good.example/rss").respond(200, text=_rss())
    respx.get("https://bad.example/rss").respond(500)
    config = make_config(tmp_path)
    config.sources.feeds.entries = [
        FeedEntry("good_feed", "https://good.example/rss", max_age_days=0),
        FeedEntry("bad_feed", "https://bad.example/rss", max_age_days=0),
    ]

    exit_code = cmd_health(config, argparse.Namespace())

    out = capsys.readouterr().out
    assert "good_feed: 3 items" in out
    assert "FAIL" in out and "bad_feed" in out
    assert "feeds: 1/2 healthy" in out
    assert exit_code == 0


@respx.mock
def test_cmd_health_exits_one_when_every_feed_fails(tmp_path, capsys):
    respx.get("https://bad.example/rss").respond(500)
    config = make_config(tmp_path)
    config.sources.feeds.entries = [
        FeedEntry("bad_feed", "https://bad.example/rss", max_age_days=0)
    ]

    exit_code = cmd_health(config, argparse.Namespace())

    assert "feeds: 0/1 healthy" in capsys.readouterr().out
    assert exit_code == 1
