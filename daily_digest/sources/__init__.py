"""Source registry: add a new source by writing a fetcher module and registering it here.
Each source fails independently — fetch_all never raises."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Callable

import httpx

from daily_digest.config import Config
from daily_digest.model import Item
from daily_digest.sources.alphaxiv import AlphaxivError, fetch_alphaxiv
from daily_digest.sources.arxiv import fetch_arxiv
from daily_digest.sources.emergent_mind import fetch_emergent_mind
from daily_digest.sources.feeds import fetch_feeds
from daily_digest.sources.hf_papers import fetch_hf_papers
from daily_digest.sources.hn import fetch_hn
from daily_digest.util import LOG

FetchFn = Callable[[httpx.Client, object], list[Item]]

REGISTRY: dict[str, FetchFn] = {
    "hn": fetch_hn,
    "hf_papers": fetch_hf_papers,
    "arxiv": fetch_arxiv,
    "emergent_mind": fetch_emergent_mind,
    "alphaxiv": fetch_alphaxiv,
    "feeds": fetch_feeds,
}


class SourceError(Exception):
    """One source failed; the rest of the digest still builds (degraded mode)."""

    def __init__(self, source: str, reason: str) -> None:
        super().__init__(f"{source}: {reason}")
        self.source = source
        self.reason = reason


def enabled_sources(config: Config) -> list[str]:
    return [
        name
        for name, fetcher in REGISTRY.items()
        if getattr(getattr(config.sources, name, None), "enabled", False)
    ]


def fetch_all(
    client: httpx.Client, config: Config
) -> tuple[list[Item], list[SourceError]]:
    items: list[Item] = []
    errors: list[SourceError] = []
    for name in enabled_sources(config):
        try:
            items.extend(REGISTRY[name](client, getattr(config.sources, name)))
        except (
            httpx.HTTPError,
            ValueError,
            KeyError,
            TypeError,
            ET.ParseError,
            AlphaxivError,
        ) as exc:
            errors.append(SourceError(name, f"{type(exc).__name__}: {exc}"))
            LOG.warning("source '%s' failed: %s: %s", name, type(exc).__name__, exc)
    return items, errors
