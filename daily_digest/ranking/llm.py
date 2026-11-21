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
from daily_digest.i18n import (
    PROMPT_LANGUAGE,
    fails_kana_gate,
    normalize_locale,
    t,
    takeaway_marker,
    truncate_overview,
)
from daily_digest.model import Item, RankedItem
from daily_digest.ranking.heuristic import default_section
from daily_digest.ranking.writer_prompts import (
    item_summary_limit,
    item_system_prompt,
    overview_system_prompt,
    overview_target_range,
)
from daily_digest.source_labels import SOURCE_LABELS, labels_for
from daily_digest.util import LOG

MAX_WHY = 140
MAX_WHY_JA = 80
MIN_SELECTION = 3
SUMMARY_WORDS = 40
SUMMARY_INPUT_CHARS = 1200
SUMMARY_INPUT_CHARS_JA = 400
MAX_OUTPUT_TOKENS = 4096
SUMMARY_BATCH_SIZE = 12

SYSTEM_PROMPT = (
    "You are the editor of a daily tech digest for an AI engineer and researcher. "
    "Their interests: {topics}.\n"
    "{reader_context}"
    "{always_rule}"
    "From the numbered candidates, select the {top_n} most valuable items for this reader today. "
    "Prefer real impact and novelty over hype. {mix_guidance} never pad with low-value items. "
    "Candidates marked [release] belong in tools_releases; keep them there. "
    "For tech_news, prefer first-party lab posts and established press/analysis; "
    "use HN when it adds a distinct technical signal rather than as the default. "
    "Prefer at most one tech_news item per source.\n"
    'Write each "why" in {language}. Keep each why under {why_limit} characters.\n'
    "Respond with ONLY a JSON object — no prose, no markdown fences — in this exact shape:\n"
    '{{"selected": [{{"id": <candidate number>, "why": "<short why in {language}>", '
    '"section": "papers|tech_news|tools_releases"}}]}}\n'
    "Order by importance. Use each candidate number at most once."
)


def mix_guidance(target: int) -> str:
    """Section mix sentence; the 12-item rendering stays byte-identical."""
    if target == 12:
        return (
            "Aim for a 7-8 papers / 3 tech news / 1-2 tools-releases mix "
            "when good candidates exist;"
        )
    if target < 6:
        return (
            "Aim for a balanced papers / tech news / tools-releases mix "
            "when good candidates exist;"
        )
    papers = max(1, round(target * 0.6))
    news = max(1, round(target * 0.25))
    tools = max(0, target - papers - news)
    if tools:
        return (
            f"Aim for about {papers} papers / {news} tech news / {tools} "
            "tools-releases when good candidates exist;"
        )
    return (
        f"Aim for about {papers} papers / {news} tech news when good candidates exist;"
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
    locale: str = "vi",
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
    if normalize_locale(locale) == "ja":
        summary = item.summary[:SUMMARY_INPUT_CHARS_JA]
    else:
        summary = " ".join(item.summary.split()[:SUMMARY_WORDS])
    signal = " ".join(signals)
    return f"[{index}] {marker}{item.title} | {label}{f' {signal}' if signal else ''} | {summary}".rstrip()


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


def _validate(
    payload: dict, index_map: dict[int, Item], locale: str = "vi"
) -> list[RankedItem]:
    loc = normalize_locale(locale) or "vi"
    why_limit = MAX_WHY_JA if loc == "ja" else MAX_WHY
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
        why = str(pick.get("why", "")).strip()[:why_limit]
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
                item=item,
                why=why or t(loc, "heuristic_top"),
                section=section,
            )
        )  # type: ignore[arg-type]
    return ranked


def rank_with_llm(
    items: list[Item],
    chat: ChatFn,
    config: Config,
    reader_context: str = "",
    *,
    target: int | None = None,
    locale: str = "vi",
) -> list[RankedItem]:
    """Rank via the chat function. Raises LlmError if the model can't produce a usable selection."""
    loc = normalize_locale(locale) or "vi"
    index_map = {index: item for index, item in enumerate(items)}
    always_rule = _ALWAYS_RULE if config.interests.always else ""
    limit = min(target or config.llm.top_n, len(items))
    system = SYSTEM_PROMPT.format(
        topics=", ".join(config.interests.topics),
        top_n=limit,
        mix_guidance=mix_guidance(limit),
        reader_context=reader_context,
        always_rule=always_rule,
        language=PROMPT_LANGUAGE[loc],
        why_limit=MAX_WHY_JA if loc == "ja" else MAX_WHY,
    )
    labels = labels_for(config)
    messages: list[dict] = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": "\n".join(
                _candidate_line(i, item, config.interests.always, labels, loc)
                for i, item in enumerate(items)
            ),
        },
    ]

    text = chat(messages)
    try:
        ranked = _validate(_extract_json(text), index_map, loc)
    except ValueError as first_error:
        LOG.debug("LLM JSON invalid (%s); asking for one repair", first_error)
        LOG.debug("editor response prefix: %.500r", text)
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
            ranked = _validate(_extract_json(text), index_map, loc)
        except ValueError as second_error:
            raise LlmError(
                f"LLM returned invalid JSON twice: {second_error}"
            ) from second_error

    if len(ranked) < min(MIN_SELECTION, limit, len(items)):
        floor = min(MIN_SELECTION, limit, len(items))
        raise LlmError(f"LLM selected only {len(ranked)} valid items (need >= {floor})")
    return ranked


SUMMARIZE_SYSTEM_PROMPT = (
    "You are the writer of a daily tech digest for an AI engineer and researcher. "
    "Their interests: {topics}.\n"
    "{reader_context}"
    "Do two things:\n"
    "1. OVERVIEW: write 3-5 short points about the whole day — the main themes "
    "across ALL items, how they connect, and the single most important takeaway "
    "for this reader. Separate points with blank lines. At every article mention, "
    "write its candidate number as [[n]] IN PLACE OF the title; the item list is "
    "0-based ([[0]] is the first item). Every numbered item must appear at least "
    "once across the overview. End with a point starting with '{takeaway_marker}'. "
    "Keep it under ~{overview_chars} characters. Write the overview in {language}. Plain text, "
    "no HTML, no markdown, no URLs, no bullet characters, and no other bracket "
    "syntax.\n"
    "2. PER-ITEM SUMMARIES: for each numbered item, a compact summary in at most "
    "{summary_limit}, 2-3 sentences, plain text (in {language}):\n"
    "- research papers: what the paper does, the key method or finding, and the "
    "practical relevance to this reader.\n"
    "- news / tools: what happened or was released, and why it matters to this reader.\n"
    "Write every per-item summary in {language}.{japanese_guard}"
    "Base everything ONLY on the provided descriptions; never invent results. "
    "If a description is empty, infer cautiously from the title and say so briefly.\n"
    "Respond with ONLY a JSON object — no prose, no markdown fences — in this exact shape:\n"
    '{{"overview": "<the day overview>", "items": [{{"id": <item number>, '
    '"summary": "<your summary>"}}]}}\n'
    "Cover every numbered item.{density_hint}"
)

MAX_SUMMARY_CHARS = 600
MAX_SUMMARY_CHARS_JA = 240
MAX_OVERVIEW_CHARS = 1600
MAX_OVERVIEW_CHARS_JA = 1200
SUMMARY_INPUT_CHARS = 1200


def overview_char_budget(item_count: int, locale: str = "vi") -> int:
    """Grow the overview budget with larger user-selected digests."""
    if normalize_locale(locale) == "ja":
        if item_count <= 12:
            return MAX_OVERVIEW_CHARS_JA
        grown = MAX_OVERVIEW_CHARS_JA + round(600 * (item_count - 12) / 18)
        return min(1800, grown)
    if item_count <= 12:
        return MAX_OVERVIEW_CHARS
    return min(3000, MAX_OVERVIEW_CHARS + 60 * (item_count - 12))


def _summary_line(
    index: int,
    ranked: RankedItem,
    labels: dict[str, str] | None = None,
    locale: str = "vi",
) -> str:
    label = (labels or _SOURCE_LABELS).get(ranked.item.source, ranked.item.source)
    description = " ".join(ranked.item.summary.split())[:SUMMARY_INPUT_CHARS]
    if not description:
        description = "(no description provided)"
    return f"[{index}] ({label}) {ranked.item.title}\n    {description}"


def _validate_summaries(
    payload: dict, index_map: dict[int, RankedItem], locale: str = "vi"
) -> dict[int, str]:
    loc = normalize_locale(locale) or "vi"
    max_chars = MAX_SUMMARY_CHARS_JA if loc == "ja" else MAX_SUMMARY_CHARS
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
        text = " ".join(str(entry.get("summary", "")).split())[:max_chars]
        if loc == "ja" and fails_kana_gate(text, loc):
            LOG.warning(
                "ja summary for item %s dropped by kana gate",
                index_map[index].item.id,
            )
            continue
        if text:
            summaries[index] = text
    return summaries


def _validate_overview(
    payload: dict, max_chars: int = MAX_OVERVIEW_CHARS, locale: str = "vi"
) -> str:
    """Clean, cap and return the day overview ('' when absent/invalid)."""
    overview = payload.get("overview")
    if not isinstance(overview, str):
        return ""
    cleaned = overview.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n[ \t]+", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    if fails_kana_gate(cleaned, locale):
        return ""
    if len(cleaned) <= max_chars:
        return cleaned
    marker = takeaway_marker(locale)
    marker_index = cleaned.rfind(marker)
    if marker_index >= 0:
        tail = cleaned[marker_index:].strip()
        head = cleaned[:marker_index].rstrip()
        if not head:
            return (
                tail
                if len(tail) <= max_chars
                else truncate_overview(tail, max_chars, locale)
            )
        allowed = max_chars - len(tail) - 2
        if allowed >= 200:
            head = truncate_overview(head, allowed, locale).rstrip()
            return head + "\n\n" + tail
    return truncate_overview(cleaned, max_chars, locale)


def write_item_summaries(
    ranked: list[RankedItem],
    chat: ChatFn,
    config: Config,
    *,
    reader_context: str = "",
    locale: str = "vi",
    deadline: float | None = None,
) -> tuple[list[RankedItem], bool]:
    """Write per-item summaries in batches; absolute indices are global."""
    if not ranked:
        return ranked, True
    loc = normalize_locale(locale) or "vi"
    index_map = {index: item for index, item in enumerate(ranked)}
    labels = labels_for(config)
    limit = item_summary_limit(config.llm.summary_max_words, loc)
    summaries: dict[int, str] = {}
    all_ok = True
    for start in range(0, len(ranked), SUMMARY_BATCH_SIZE):
        if deadline is not None and time.monotonic() >= deadline:
            LOG.warning("writer v2 deadline exceeded before item batch %d", start)
            all_ok = False
            break
        batch = ranked[start : start + SUMMARY_BATCH_SIZE]
        messages: list[dict] = [
            {
                "role": "system",
                "content": item_system_prompt(
                    loc,
                    topics=", ".join(config.interests.topics),
                    reader_context=reader_context,
                    limit=limit,
                ),
            },
            {
                "role": "user",
                "content": "\n".join(
                    _summary_line(index, item, labels, loc)
                    for index, item in enumerate(batch, start=start)
                ),
            },
        ]

        def parse(text: str) -> dict[int, str]:
            payload = _extract_json(text)
            parsed = _validate_summaries(payload, index_map, loc)
            return {
                index: value
                for index, value in parsed.items()
                if start <= index < start + len(batch)
            }

        try:
            text = chat(messages)
            batch_summaries = parse(text)
        except (ValueError, json.JSONDecodeError) as first_error:
            LOG.debug(
                "writer v2 item batch %d invalid (%s); asking for one repair",
                start,
                first_error,
            )
            LOG.debug("writer v2 item response prefix: %.500r", text)
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
            try:
                batch_summaries = parse(chat(messages))
            except (ValueError, json.JSONDecodeError) as second_error:
                LOG.warning(
                    "writer v2 item batch %d failed: %s; keeping raw abstracts",
                    start,
                    second_error,
                )
                all_ok = False
                continue
        summaries.update(batch_summaries)
        if len(batch_summaries) < len(batch):
            all_ok = False
    return (
        [
            dataclasses.replace(item, llm_summary=summaries.get(index, ""))
            for index, item in enumerate(ranked)
        ],
        all_ok,
    )


def write_overview(
    ranked: list[RankedItem],
    chat: ChatFn,
    config: Config,
    *,
    reader_context: str = "",
    locale: str = "vi",
    deadline: float | None = None,
) -> str:
    """Write an independent synthesis overview; returns "" on failure."""
    if not ranked:
        return ""
    if deadline is not None and time.monotonic() >= deadline:
        LOG.warning("writer v2 deadline exceeded before overview")
        return ""
    loc = normalize_locale(locale) or "vi"
    budget = overview_char_budget(len(ranked), loc)
    target = overview_target_range(len(ranked), loc)
    lines = []
    for index, item in enumerate(ranked):
        summary = item.llm_summary or item.item.summary
        lines.append(
            f"[{index}] ({item.section}) {item.item.title}\n"
            f"    summary: {summary[:300]}\n"
            f"    source: {item.item.summary[:300]}"
        )
    messages: list[dict] = [
        {
            "role": "system",
            "content": overview_system_prompt(
                loc,
                topics=", ".join(config.interests.topics),
                reader_context=reader_context,
                target=target,
                hard_cap=budget,
                takeaway=takeaway_marker(loc),
                item_count=len(ranked),
            ),
        },
        {"role": "user", "content": "\n".join(lines)},
    ]

    def parse(text: str) -> str:
        payload = _extract_json(text)
        return _validate_overview(payload, budget, loc)

    try:
        text = chat(messages)
        overview = parse(text)
    except (ValueError, json.JSONDecodeError) as first_error:
        LOG.debug("writer v2 overview invalid (%s); asking for one repair", first_error)
        LOG.debug("writer v2 overview response prefix: %.500r", text)
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
        try:
            overview = parse(chat(messages))
        except (ValueError, json.JSONDecodeError) as second_error:
            LOG.warning("writer v2 overview failed: %s", second_error)
            return ""
    if not overview:
        LOG.warning("writer v2 overview was empty")
    return overview


def _summarize_v2(
    ranked: list[RankedItem],
    chat: ChatFn,
    config: Config,
    reader_context: str,
    locale: str,
    deadline: float | None,
) -> tuple[list[RankedItem], str]:
    localized, _ = write_item_summaries(
        ranked,
        chat,
        config,
        reader_context=reader_context,
        locale=locale,
        deadline=deadline,
    )
    overview = write_overview(
        localized,
        chat,
        config,
        reader_context=reader_context,
        locale=locale,
        deadline=deadline,
    )
    return localized, overview


def summarize_with_llm(
    ranked: list[RankedItem],
    chat: ChatFn,
    config: Config,
    reader_context: str = "",
    locale: str = "vi",
    *,
    deadline: float | None = None,
) -> tuple[list[RankedItem], str]:
    """Write the day overview + reader-facing summaries.

    ``writer_v2`` keeps the two outputs independent; the default path remains
    the original single JSON call for rollback.
    """
    if not ranked:
        return ranked, ""
    if config.llm.writer_v2:
        return _summarize_v2(ranked, chat, config, reader_context, locale, deadline)
    loc = normalize_locale(locale) or "vi"
    language = PROMPT_LANGUAGE[loc]
    summary_limit = (
        "150-220 Japanese characters"
        if loc == "ja"
        else f"{config.llm.summary_max_words} words"
    )
    japanese_guard = (
        "\nUse natural Japanese; keep standard technical names in Latin script. "
        if loc == "ja"
        else ""
    )
    index_map = {index: item for index, item in enumerate(ranked)}
    labels = labels_for(config)
    budget = overview_char_budget(len(ranked), loc)
    density_hint = (
        " This is a dense digest: keep each summary tight so the JSON fits."
        if len(ranked) > 16
        else ""
    )
    messages: list[dict] = [
        {
            "role": "system",
            "content": SUMMARIZE_SYSTEM_PROMPT.format(
                topics=", ".join(config.interests.topics),
                summary_limit=summary_limit,
                language=language,
                reader_context=reader_context,
                overview_chars=budget,
                density_hint=density_hint,
                takeaway_marker=takeaway_marker(loc),
                japanese_guard=japanese_guard,
            ),
        },
        {
            "role": "user",
            "content": "\n".join(
                _summary_line(index, item, labels, loc)
                for index, item in enumerate(ranked)
            ),
        },
    ]
    overview = ""
    try:
        text = chat(messages)
        try:
            payload = _extract_json(text)
            summaries = _validate_summaries(payload, index_map, loc)
            overview = _validate_overview(payload, budget, loc)
        except ValueError as first_error:
            LOG.debug("summary JSON invalid (%s); asking for one repair", first_error)
            LOG.debug("writer response prefix: %.500r", text)
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
            summaries = _validate_summaries(payload, index_map, loc)
            overview = _validate_overview(payload, budget, loc)
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
            "max_tokens": MAX_OUTPUT_TOKENS,
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
                choice = data["choices"][0]
                finish_reason = choice.get("finish_reason")
                usage = data.get("usage") or {}
                LOG.info(
                    "LLM response model=%s finish_reason=%s prompt_tokens=%s "
                    "completion_tokens=%s total_tokens=%s",
                    self.model,
                    finish_reason,
                    usage.get("prompt_tokens") if isinstance(usage, dict) else None,
                    usage.get("completion_tokens") if isinstance(usage, dict) else None,
                    usage.get("total_tokens") if isinstance(usage, dict) else None,
                )
                if finish_reason == "length":
                    LOG.warning(
                        "LLM response was truncated (model=%s); increase the "
                        "per-stage output budget before treating the JSON as valid",
                        self.model,
                    )
                return str(choice["message"]["content"])
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
