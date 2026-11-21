"""Digest-size policy and preference storage."""

from __future__ import annotations

import json

import pytest

from daily_digest.digest_size import (
    DEFAULT_DIGEST_SIZE,
    DigestSizeError,
    clear_digest_size,
    load_preferences,
    normalize_digest_size,
    resolve_digest_size,
    save_digest_size,
    stored_digest_size,
)
from helpers import make_config


def test_normalize_range_and_types():
    assert normalize_digest_size(1) == 1
    assert normalize_digest_size(12) == 12
    assert normalize_digest_size(30) == 30
    assert normalize_digest_size("12") == 12

    for value in (0, 31, -1, True, False, None, "nope"):
        with pytest.raises(DigestSizeError):
            normalize_digest_size(value)


def test_resolve_precedence_and_cap(tmp_path):
    config = make_config(tmp_path)
    config.llm.top_n = 8
    config.llm.max_pool = 20

    assert resolve_digest_size(config, {}, None) == 8
    assert resolve_digest_size(config, {"digest_size": 16}, None) == 16
    assert resolve_digest_size(config, {"digest_size": 16}, 4) == 4
    assert resolve_digest_size(config, {"digest_size": 16}, 30) == 20
    assert resolve_digest_size(config, {"digest_size": "bad"}, None) == 8

    config.llm.max_pool = 10
    assert resolve_digest_size(config, {"digest_size": 30}, None) == 10
    assert resolve_digest_size(config, {}, 30) == 10


def test_resolve_falls_back_when_config_is_invalid(tmp_path):
    config = make_config(tmp_path)
    config.llm.top_n = 31
    assert resolve_digest_size(config, {}) == DEFAULT_DIGEST_SIZE


def test_save_and_clear_preserve_other_preferences(tmp_path):
    config = make_config(tmp_path)
    path = config.preferences_path

    save_digest_size(path, 18)
    assert json.loads(path.read_text(encoding="utf-8")) == {"digest_size": 18}

    path.write_text(json.dumps({"digest_size": 18, "theme": "dark"}), encoding="utf-8")
    clear_digest_size(path)
    assert json.loads(path.read_text(encoding="utf-8")) == {"theme": "dark"}


def test_load_preferences_handles_missing_and_corrupt_files(tmp_path):
    config = make_config(tmp_path)
    assert load_preferences(config.preferences_path) == {}

    config.preferences_path.write_text("{broken", encoding="utf-8")
    assert load_preferences(config.preferences_path) == {}
    assert (tmp_path / "preferences.json.corrupt").exists()


def test_stored_digest_size_is_tolerant():
    assert stored_digest_size({}) is None
    assert stored_digest_size({"digest_size": 7}) == 7
    assert stored_digest_size({"digest_size": "bad"}) is None
