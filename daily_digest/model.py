"""Core data model."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

Section = Literal["papers", "tech_news", "tools_releases"]
SECTIONS: tuple[Section, ...] = ("papers", "tech_news", "tools_releases")

SECTION_TITLES: dict[Section, str] = {
    "papers": "Research Papers",
    "tech_news": "Tech News",
    "tools_releases": "Tools & Releases",
}


@dataclass(frozen=True)
class Item:
    """One candidate from one source. `id` is the canonical uid (see normalize.item_uid)."""

    id: str
    title: str
    url: str
    source: str  # "hn" | "arxiv" | "hf_papers" | "emergentmind" | "alphaxiv" | ...
    points: int | None = None
    published: datetime | None = None
    summary: str = ""
    citations: int | None = None  # from OpenAlex enrichment (None = not looked up)
    # Optional source-declared section (e.g. GitHub releases -> tools_releases).
    # The editor LLM may still reclassify a non-paper item as tech_news/tool.
    section_hint: Section | None = None


@dataclass(frozen=True)
class RankedItem:
    """An item selected for today's digest, with the editor's one-line justification
    and (when the summarizer LLM ran) a reader-facing summary of the work."""

    item: Item
    why: str
    section: Section
    llm_summary: str = (
        ""  # written by the summarizer LLM; empty -> fall back to item.summary
    )
    backfilled: bool = False  # came from a previous-day archive


@dataclass(frozen=True)
class Notice:
    """One localized-at-render status message; params are format arguments."""

    key: str
    params: Mapping[str, object] = field(default_factory=dict)
    text: str = ""


@dataclass
class RunResult:
    digest_path: Path | None = None
    mode: str = "skipped"  # "llm" | "heuristic" | "skipped" | "nothing-new"
    degraded: bool = False
    sources_failed: list[str] = field(default_factory=list)
    item_count: int = 0
    exit_code: int = 0
    message: str = ""
