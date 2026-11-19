"""F4: reader profile context.

The user writes free text in profile.md about their current work; a capped
excerpt is injected into the editor/writer/ask prompts via the shared
reader_context block. Total function: any failure -> "" + warning, never blocks.
"""

from __future__ import annotations

from pathlib import Path

from daily_digest.config import Config
from daily_digest.util import LOG, PROJECT_ROOT


def load_profile(config: Config) -> str:
    """Load and cap the reader's profile text. Returns '' when disabled/missing."""
    path = Path(config.llm.profile_file)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not config.llm.profile_file:
        return ""
    if not path.exists():
        LOG.info("profile file not found at %s (llm.profile_file) — skipping", path)
        return ""
    try:
        text = " ".join(path.read_text(encoding="utf-8").split())
    except OSError as exc:
        LOG.warning("profile file unreadable (%s): %s — skipping", path, exc)
        return ""
    if not text:
        return ""
    return _cap(text, config.llm.profile_max_chars)


def _cap(text: str, max_chars: int) -> str:
    """Truncate on a word boundary; never split a word in half."""
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    last_space = cut.rfind(" ")
    if last_space > max_chars // 2:  # a sensible boundary exists
        cut = cut[:last_space]
    return cut.rstrip() + "…"


def profile_block(profile: str) -> str:
    """The reader_context contribution of the profile. '' when empty.
    Built by concatenation only — profile text may contain any braces."""
    if not profile:
        return ""
    return "About the reader's current work, in their own words: " + profile + "\n"
