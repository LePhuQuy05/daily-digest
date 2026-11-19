"""Shared fixtures. The autouse guards prevent tests from ever launching real
desktop windows or pythonw subprocesses, hitting external APIs, or leaking env
state (config-loading tests pull the developer's real .env into os.environ)."""

import os

import pytest

import daily_digest.pipeline as pipeline


@pytest.fixture(autouse=True)
def _no_real_popup(monkeypatch):
    monkeypatch.setattr(pipeline, "spawn_popup_detached", lambda path: True)


@pytest.fixture(autouse=True)
def _no_real_enrichment(monkeypatch):
    # enrich_citations opens its own HTTP client; neutralize it for every test so
    # the suite never hits OpenAlex. Dedicated enrich tests mock at the HTTP layer.
    monkeypatch.setattr(pipeline, "enrich_citations", lambda items, config: items)


@pytest.fixture(autouse=True)
def _environ_snapshot():
    """Isolate os.environ per test: load_config() loads the developer's real .env
    (real API keys) into the process env; without a snapshot those keys leak into
    later tests and make them hit live endpoints."""
    snapshot = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(snapshot)
