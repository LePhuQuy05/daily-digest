"""Digest-size policy and local preference storage.

The digest size is a user preference, not pipeline state: keeping it in a
separate JSON file avoids racing the run's ``state.json`` writes.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from daily_digest.i18n import normalize_locale
from daily_digest.util import LOG, load_json, save_json

if TYPE_CHECKING:  # pragma: no cover - typing only
    from daily_digest.config import Config

DEFAULT_DIGEST_SIZE = 12
MIN_DIGEST_SIZE = 1
MAX_DIGEST_SIZE = 30


class DigestSizeError(ValueError):
    """Invalid digest-size value."""


def _as_int(value: object) -> int:
    if isinstance(value, bool):
        raise DigestSizeError("digest size must be an integer, not a boolean")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    raise DigestSizeError(f"digest size must be an integer, got {value!r}")


def normalize_digest_size(value: object) -> int:
    """Return a valid 1..30 integer or raise DigestSizeError."""
    size = _as_int(value)
    if not MIN_DIGEST_SIZE <= size <= MAX_DIGEST_SIZE:
        raise DigestSizeError(
            f"digest size must be {MIN_DIGEST_SIZE}..{MAX_DIGEST_SIZE}, got {size}"
        )
    return size


def effective_max(config: Config) -> int:
    """The configured pool cannot provide more than this many items."""
    return max(MIN_DIGEST_SIZE, min(MAX_DIGEST_SIZE, int(config.llm.max_pool)))


def stored_digest_size(preferences: dict) -> int | None:
    """Read a stored preference, tolerating old/corrupt values."""
    value = preferences.get("digest_size")
    if value is None:
        return None
    try:
        return normalize_digest_size(value)
    except DigestSizeError as exc:
        LOG.warning("preferences.digest_size ignored: %s", exc)
        return None


def resolve_digest_size(
    config: Config,
    preferences: dict,
    override: int | None = None,
) -> int:
    """Resolve CLI override > stored preference > config > default."""
    cap = effective_max(config)
    if override is not None:
        try:
            requested = normalize_digest_size(override)
        except DigestSizeError as exc:
            raise DigestSizeError(str(exc)) from exc
        if requested > cap:
            LOG.warning(
                "digest size %d exceeds max_pool cap %d; using %d", requested, cap, cap
            )
            return cap
        return requested

    stored = stored_digest_size(preferences)
    if stored is not None:
        if stored > cap:
            LOG.warning(
                "stored digest size %d exceeds max_pool cap %d; using %d",
                stored,
                cap,
                cap,
            )
            return cap
        return stored

    try:
        configured = normalize_digest_size(config.llm.top_n)
    except DigestSizeError as exc:
        LOG.warning(
            "llm.top_n invalid (%s); using default %d", exc, DEFAULT_DIGEST_SIZE
        )
        configured = DEFAULT_DIGEST_SIZE
    if configured > cap:
        LOG.warning(
            "llm.top_n %d exceeds max_pool cap %d; using %d", configured, cap, cap
        )
        return cap
    return configured


def load_preferences(path: Path) -> dict:
    """Load preferences; a missing/corrupt file is treated as empty."""
    return load_json(path)


def save_preferences(path: Path, **updates: object) -> None:
    """Atomically merge preferences, preserving unknown keys."""
    preferences = load_json(path)
    preferences.update(updates)
    save_json(path, preferences)


def save_digest_size(path: Path, size: int) -> None:
    """Save one preference atomically, preserving unknown keys."""
    value = normalize_digest_size(size)
    save_preferences(path, digest_size=value)


def set_language(path: Path, locale: str) -> None:
    """Persist an explicit locale preference."""
    normalized = normalize_locale(locale)
    if normalized is None:
        raise ValueError(f"unsupported locale: {locale!r}")
    save_preferences(path, language=normalized)


def clear_language(path: Path) -> None:
    """Remove the stored locale preference, preserving other keys."""
    preferences = load_json(path)
    if "language" not in preferences:
        return
    preferences.pop("language", None)
    save_json(path, preferences)


def clear_digest_size(path: Path) -> None:
    """Remove the size preference, preserving other keys."""
    preferences = load_json(path)
    if "digest_size" not in preferences:
        return
    preferences.pop("digest_size", None)
    save_json(path, preferences)
