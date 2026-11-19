"""LLM ranking via an OpenAI-compatible endpoint (default: OpenCode Go, GLM 5.3).

Contract details that matter:
- Candidates are numbered with synthetic integer indices; the model echoes indices only.
  URLs and titles in the digest always come from our own data, never from the model.
- The model's JSON is parsed defensively: markdown fences stripped, unknown/duplicate
  indices dropped, sections clamped, 'why' truncated. One repair retry, then LlmError.
"""

from __future__ import annotations

import dataclasses
import json
import re
import time
from typing import Protocol

import httpx

from daily_digest.config import Config
from daily_digest.model import Item, RankedItem
from daily_digest.ranking.heuristic import default_section
from daily_digest.source_labels import SOURCE_LABELS, labels_for
from daily_digest.util import LOG

MAX_WHY = 140
MIN_SELECTION = 3
SUMMARY_WORDS = 40

SYSTEM_PROMPT = (
    "You are the editor of a daily tech digest for an AI engineer and researcher. "
    "Their interests: {topics}.\n"
    "{reader_context}"
    "{always_rule}"
    "From the numbered candidates, select the {top_n} most valuable items for this reader today. "
    "Prefer real impact and novelty over hype. Aim for a 7-8 papers / 3 tech news / 1-2 "
    "tools-releases mix when good candidates exist; never pad with low-value items. "
    "Candidates marked [release] belong in tools_releases; keep them there. "
    "For tech_news, prefer first-party lab posts and established press/analysis; "
    "use HN when it adds a distinct technical signal rather than as the default.\n"
    "Respond with ONLY a JSON object — no prose, no markdown fences — in this exact shape:\n"
    '{{"selected": [{{"id": <candidate number>, "why": "<=140 chars why it matters to this reader", '
    '"section": "papers|tech_news|tools_releases"}}]}}\n'
    "Order by importance. Use each candidate number at most once."
)

_ALWAYS_RULE = (
    "Entries marked ★ALWAYS match the reader's must-see keywords; "
    "include them unless clearly irrelevant.\n"
)

_SOURCE_LABELS = SOURCE_LABELS  # backwards-compatible alias for tests/imports


class LlmError(Exception):
    """LLM ranking failed; pipeline falls back to heuristic ranking."""


class ChatFn(Protocol):
    def __call__(self, messages: list[dict]) -> str: ...  # pragma: no cover


def _candidate_line(
    index: int,
    item: Item,
    always: list[str] | None = None,
    labels: dict[str, str] | None = None,
) -> str:
    from daily_digest.rules import always_match

    marker = ""
    if always and always_match(item, always):
        marker = "★ALWAYS "  # F5: reader's explicit must-see keyword
    label = (labels or _SOURCE_LABELS).get(item.source, item.source)
    if item.section_hint == "tools_releases":
        label += " [release]"
    signals = []
    if item.points:
        signals.append(f"{item.points} pts")
    if item.citations:
        signals.append(f"{item.citations} citations")
    words = " ".join(item.summary.split()[:SUMMARY_WORDS])
    signal = " ".join(signals)
    return f"[{index}] {marker}{item.title} | {label}{f' {signal}' if signal else ''} | {words}".rstrip()


def _extract_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object found in response")
    payload = json.loads(cleaned[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("JSON payload is not an object")
    return payload


def _validate(payload: dict, index_map: dict[int, Item]) -> list[RankedItem]:
    picked: set[int] = set()
    ranked: list[RankedItem] = []
    for pick in payload.get("selected", []):
        if not isinstance(pick, dict):
            continue
        try:
            index = int(pick["id"])
        except (KeyError, TypeError, ValueError):
            continue
        if index not in index_map or index in picked:
            continue
        picked.add(index)
        item = index_map[index]
        why = str(pick.get("why", "")).strip()[:MAX_WHY]
        # Sections must be consistent with the source: paper sources stay papers;
        # everything else is news or a tool release. Bogus values clamp to the
        # source's hint/default (GitHub releases -> tools_releases).
        if item.section_hint == "tools_releases":
            allowed = ("tools_releases",)  # GitHub release feeds are authoritative
        elif default_section(item) == "papers":
            allowed = ("papers",)
        else:
            allowed = ("tech_news", "tools_releases")
        section = str(pick.get("section", "")).strip().lower()
        if section not in allowed:
            section = default_section(item)
        ranked.append(
            RankedItem(
                item=item, why=why or "picked by the LLM editor", section=section
            )
        )  # type: ignore[arg-type]
    return ranked


def rank_with_llm(
    items: list[Item], chat: ChatFn, config: Config, reader_context: str = ""
) -> list[RankedItem]:
    """Rank via the chat function. Raises LlmError if the model can't produce a usable selection."""
    index_map = {index: item for index, item in enumerate(items)}
    always_rule = _ALWAYS_RULE if config.interests.always else ""
    system = SYSTEM_PROMPT.format(
        topics=", ".join(config.interests.topics),
        top_n=min(config.llm.top_n, len(items)),
        reader_context=reader_context,
        always_rule=always_rule,
    )
    labels = labels_for(config)
    messages: list[dict] = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": "\n".join(
                _candidate_line(i, item, config.interests.always, labels)
                for i, item in enumerate(items)
            ),
        },
    ]

    text = chat(messages)
    try:
        ranked = _validate(_extract_json(text), index_map)
    except ValueError as first_error:
        LOG.debug("LLM JSON invalid (%s); asking for one repair", first_error)
        messages.extend(
            [
                {"role": "assistant", "content": text},
                {
                    "role": "user",
                    "content": f"Your previous answer was not valid JSON ({first_error}). "
                    "Respond again with ONLY the JSON object.",
                },
            ]
        )
        text = chat(messages)
        try:
            ranked = _validate(_extract_json(text), index_map)
        except ValueError as second_error:
            raise LlmError(
                f"LLM returned invalid JSON twice: {second_error}"
            ) from second_error

    if len(ranked) < MIN_SELECTION:
        raise LlmError(
            f"LLM selected only {len(ranked)} valid items (need >= {MIN_SELECTION})"
        )
    return ranked


SUMMARIZE_SYSTEM_PROMPT = (
    "You are the writer of a daily tech digest for an AI engineer and researcher. "
    "Their interests: {topics}.\n"
    "{reader_context}"
    "Do two things:\n"
    "1. OVERVIEW: write a 2-4 sentence synthesis of the whole day — the main themes "
    "across ALL items, how they connect, and the single most important takeaway for "
    "this reader. Write the overview in {language}. Plain text, no bullet characters.\n"
    "2. PER-ITEM SUMMARIES: for each numbered item, a compact summary in at most "
    "{max_words} words, 2-3 sentences, plain text (in English):\n"
    "- research papers: what the paper does, the key method or finding, and the "
    "practical relevance to this reader.\n"
    "- news / tools: what happened or was released, and why it matters to this reader.\n"
    "Base everything ONLY on the provided descriptions; never invent results. "
    "If a description is empty, infer cautiously from the title and say so briefly.\n"
    "Respond with ONLY a JSON object — no prose, no markdown fences — in this exact shape:\n"
    '{{"overview": "<the day overview>", "items": [{{"id": <item number>, '
    '"summary": "<your summary>"}}]}}\n'
    "Cover every numbered item."
)

MAX_SUMMARY_CHARS = 600
MAX_OVERVIEW_CHARS = 900
SUMMARY_INPUT_CHARS = 1200
_LANGUAGE_NAME = {
    "vi": "Vietnamese",
    "en": "English",
    "": "English",
}


def _summary_line(
    index: int, ranked: RankedItem, labels: dict[str, str] | None = None
) -> str:
    label = (labels or _SOURCE_LABELS).get(ranked.item.source, ranked.item.source)
    description = " ".join(ranked.item.summary.split())[:SUMMARY_INPUT_CHARS]
    if not description:
        description = "(no description provided)"
    return f"[{index}] ({label}) {ranked.item.title}\n    {description}"


def _validate_summaries(
    payload: dict, index_map: dict[int, RankedItem]
) -> dict[int, str]:
    summaries: dict[int, str] = {}
    entries = payload.get("items", [])
    if not isinstance(entries, list):
        raise ValueError("'items' is not a list")
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        try:
            index = int(entry["id"])
        except (KeyError, TypeError, ValueError):
            continue
        if index not in index_map:
            continue
        text = " ".join(str(entry.get("summary", "")).split())[:MAX_SUMMARY_CHARS]
        if text:
            summaries[index] = text
    return summaries


def _validate_overview(payload: dict) -> str:
    """Clean, cap and return the day overview ('' when absent/invalid).
    Truncation is word-boundary + ellipsis — never cut mid-word (a truncated
    Vietnamese sentence like "...cần đư" undermines trust)."""
    overview = payload.get("overview")
    if not isinstance(overview, str):
        return ""
    cleaned = " ".join(overview.split())
    if len(cleaned) <= MAX_OVERVIEW_CHARS:
        return cleaned
    cut = cleaned[:MAX_OVERVIEW_CHARS]
    last_space = cut.rfind(" ")
    if last_space > MAX_OVERVIEW_CHARS // 2:
        cut = cut[:last_space]
    return cut.rstrip(" ,;:.-") + "…"


def summarize_with_llm(
    ranked: list[RankedItem], chat: ChatFn, config: Config, reader_context: str = ""
) -> tuple[list[RankedItem], str]:
    """Write the day overview + a reader-facing summary per item (one batched call).

    Total function: on any failure it logs a warning and returns the input unchanged
    with an empty overview (the digest then falls back to raw abstracts and the
    mechanical overview)."""
    if not ranked:
        return ranked, ""
    language = _LANGUAGE_NAME.get(config.llm.overview_language.strip().lower())
    if language is None:
        language = config.llm.overview_language.strip() or "English"
    index_map = {index: item for index, item in enumerate(ranked)}
    labels = labels_for(config)
    messages: list[dict] = [
        {
            "role": "system",
            "content": SUMMARIZE_SYSTEM_PROMPT.format(
                topics=", ".join(config.interests.topics),
                max_words=config.llm.summary_max_words,
                language=language,
                reader_context=reader_context,
            ),
        },
        {
            "role": "user",
            "content": "\n".join(
                _summary_line(index, item, labels) for index, item in enumerate(ranked)
            ),
        },
    ]
    overview = ""
    try:
        text = chat(messages)
        try:
            payload = _extract_json(text)
            summaries = _validate_summaries(payload, index_map)
            overview = _validate_overview(payload)
        except ValueError as first_error:
            LOG.debug("summary JSON invalid (%s); asking for one repair", first_error)
            messages.extend(
                [
                    {"role": "assistant", "content": text},
                    {
                        "role": "user",
                        "content": f"Your previous answer was not valid JSON ({first_error}). "
                        "Respond again with ONLY the JSON object.",
                    },
                ]
            )
            text = chat(messages)
            payload = _extract_json(text)
            summaries = _validate_summaries(payload, index_map)
            overview = _validate_overview(payload)
    except (LlmError, ValueError) as exc:
        LOG.warning("LLM summarization failed (%s); keeping original abstracts", exc)
        return ranked, ""

    enriched = [
        dataclasses.replace(ranked_item, llm_summary=summaries.get(index, ""))
        for index, ranked_item in enumerate(ranked)
    ]
    covered = sum(1 for item in enriched if item.llm_summary)
    LOG.info(
        "LLM summaries written for %d/%d items; overview: %s",
        covered,
        len(enriched),
        "yes" if overview else "missing",
    )
    return enriched, overview


class LlmClient:
    """Minimal OpenAI-compatible chat client with the OpenCode session header."""

    def __init__(
        self, config: Config, api_key: str, session_id: str, model: str | None = None
    ) -> None:
        self.config = config
        self.api_key = api_key
        self.session_id = session_id
        self.model = model or config.llm.model
        self.url = config.llm.base_url.rstrip("/") + config.llm.chat_path

    def chat(self, messages: list[dict]) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "x-opencode-session": self.session_id,
        }
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": self.config.llm.temperature,
        }
        backoffs = (2, 8)
        last_error: Exception | None = None
        for attempt in range(self.config.llm.max_retries + 1):
            try:
                with httpx.Client(timeout=self.config.llm.timeout_seconds) as client:
                    response = client.post(self.url, headers=headers, json=body)
                if response.status_code in (401, 403, 404):
                    detail = response.text[:200]
                    raise LlmError(
                        f"HTTP {response.status_code} from LLM endpoint — check api key, base_url "
                        f"and model '{self.model}'. {detail}"
                    )
                if response.status_code == 429 or response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"HTTP {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                response.raise_for_status()
                data = response.json()
                return str(data["choices"][0]["message"]["content"])
            except LlmError:
                raise
            except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
                last_error = exc
                if attempt < self.config.llm.max_retries:
                    delay = backoffs[min(attempt, len(backoffs) - 1)]
                    LOG.warning(
                        "LLM attempt %d failed (%s); retrying in %ss",
                        attempt + 1,
                        exc,
                        delay,
                    )
                    time.sleep(delay)
        raise LlmError(
            f"LLM unreachable after {self.config.llm.max_retries + 1} attempts: {last_error}"
        )
