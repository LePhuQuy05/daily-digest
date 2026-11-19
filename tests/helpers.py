"""Shared test helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from daily_digest.config import Config
from daily_digest.model import Item
from daily_digest.util import PROJECT_ROOT

FIXTURES = Path(__file__).parent / "fixtures"


def make_config(tmp_path: Path) -> Config:
    """Isolated config: tmp state/output/logs/feedback, real template, no network delays."""
    config = Config()
    config.output_dir = tmp_path / "output"
    config.state_path = tmp_path / "state.json"
    config.log_dir = tmp_path / "logs"
    config.feedback_path = tmp_path / "feedback.jsonl"
    config.media.enabled = False  # tests stay offline; media tests opt in
    config.template_path = PROJECT_ROOT / "templates" / "digest.html.j2"
    config.sources.arxiv.pause_seconds = 0.0
    return config


def make_item(
    *,
    id: str,
    title: str,
    url: str,
    source: str = "hn",
    points: int | None = None,
    summary: str = "",
) -> Item:
    return Item(
        id=id,
        title=title,
        url=url,
        source=source,
        points=points,
        published=datetime(2026, 11, 18, 2, 0, tzinfo=timezone.utc),
        summary=summary,
    )


class FakeChat:
    """Callable that stands in for LlmClient.chat."""

    def __init__(self, responses: list[str] | str) -> None:
        self.responses = [responses] if isinstance(responses, str) else list(responses)
        self.calls: list[list[dict]] = []

    def __call__(self, messages: list[dict]) -> str:
        self.calls.append(messages)
        return (
            self.calls
            and self.responses[min(len(self.calls) - 1, len(self.responses) - 1)]
        )


class FakeLlmClient:
    """Stands in for LlmClient in run_day/select (has .chat)."""

    def __init__(self, responses: list[str] | str) -> None:
        self.chat = FakeChat(responses)


def llm_ok_json(count: int = 8, section: str = "papers") -> str:
    picks = ",".join(
        f'{{"id": {i}, "why": "why it matters {i}", "section": "{section}"}}'
        for i in range(count)
    )
    return f'{{"selected": [{picks}]}}'
