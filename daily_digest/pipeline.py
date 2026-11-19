"""The daily pipeline: fetch -> merge/dedupe -> seen-set -> rank -> render -> notify -> state.

Exit codes: 0 clean · 1 degraded (partial sources, heuristic mode, notify failure,
zero items from healthy sources) · 2 fatal (config, all sources failed).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

import httpx

from daily_digest.config import Config
from daily_digest.enrich import enrich_citations
from daily_digest.feedback import (
    FeedbackAggregate,
    aggregate,
    pinned_items,
    read_feedback,
    reader_context_block,
    topic_adjustments,
)
from daily_digest.model import Item, RunResult, SECTIONS
from daily_digest.normalize import item_uid
from daily_digest.notify import notify
from daily_digest.popup import spawn_popup_detached
from daily_digest.profile import load_profile
from daily_digest.ranking import select
from daily_digest.ranking.heuristic import (
    balanced_pool,
    heuristic_overview,
    overview_label,
)
from daily_digest.media import collect_images
from daily_digest.ranking.llm import LlmClient, summarize_with_llm
from daily_digest.render import build_digest_data, render_digest, write_digest
from daily_digest.rules import apply_mute, log_mute_summary
from daily_digest.sources import SourceError, enabled_sources, fetch_all
from daily_digest.source_labels import labels_for
from daily_digest.util import LOG, load_json, save_json, today_str


def merge_items(items: list[Item]) -> list[Item]:
    """Merge the same story/paper across sources into one Item.

    Provenance priority is deterministic regardless of arrival order:
    hf_papers (curated upvotes) > alphaxiv (community upvotes) >
    emergentmind (cross-platform trending) > everything else.
    Points and citations take the max; summaries keep the longer one.
    """
    priority = {"hf_papers": 4, "alphaxiv": 3, "emergentmind": 2}

    def rank(source: str) -> int:
        return priority.get(source, 1)

    merged: dict[str, Item] = {}
    for item in items:
        uid = item_uid(item)
        existing = merged.get(uid)
        if existing is None:
            merged[uid] = item
            continue
        keep, other = (
            (existing, item)
            if rank(existing.source) >= rank(item.source)
            else (item, existing)
        )
        points = max(
            (p for p in (keep.points, other.points) if p is not None), default=None
        )
        citations = max(
            (c for c in (keep.citations, other.citations) if c is not None),
            default=None,
        )
        summary = (
            keep.summary if len(keep.summary) >= len(other.summary) else other.summary
        )
        published = max(
            (p for p in (keep.published, other.published) if p is not None),
            default=None,
        )
        merged[uid] = Item(
            id=uid,
            title=keep.title or other.title,
            url=keep.url,
            source=keep.source,
            points=points,
            published=published,
            summary=summary,
            citations=citations,
            section_hint=keep.section_hint or other.section_hint,
        )
    return list(merged.values())


def _prune_seen(seen: dict[str, str], today: str, window_days: int) -> dict[str, str]:
    cutoff = (
        datetime.strptime(today, "%Y-%m-%d") - timedelta(days=window_days)
    ).strftime("%Y-%m-%d")
    return {uid: date for uid, date in seen.items() if date >= cutoff}


def run_day(
    config: Config,
    date: str | None = None,
    *,
    http: httpx.Client | None = None,
    llm_client: LlmClient | None = None,
    force: bool = False,
    notify_enabled: bool = True,
    notify_fn: Callable[..., None] = notify,
    summary_client: LlmClient | None = None,
) -> RunResult:
    date = date or today_str()
    state = load_json(config.state_path)
    days: dict = state.setdefault("days", {})

    entry = days.get(date, {})
    if entry.get("notified") and not force:
        digest_path = Path(entry["digest_path"]) if entry.get("digest_path") else None
        LOG.info(
            "digest for %s already delivered — nothing to do (use --force to redo)",
            date,
        )
        return RunResult(
            digest_path=digest_path,
            mode="skipped",
            exit_code=0,
            message="already delivered",
        )

    # 1. Fetch (per-source isolation)
    with http or httpx.Client(timeout=30.0, follow_redirects=True) as client:
        items, errors = fetch_all(client, config)
    failed = [error.source for error in errors]

    enabled = enabled_sources(config)
    if not items and len(failed) >= len(enabled) and enabled:
        LOG.error("all sources failed: %s", failed)
        return RunResult(
            degraded=True,
            sources_failed=failed,
            exit_code=2,
            message="all sources failed",
        )
    if not items:
        LOG.warning("no candidate items today (failed=%s)", failed)
        return RunResult(
            degraded=bool(failed),
            sources_failed=failed,
            exit_code=1,
            message="no candidates today",
        )

    # 2. Merge duplicates, then drop items already shown on previous days
    items = merge_items(items)
    seen: dict[str, str] = state.get("seen", {})
    fresh = [item for item in items if seen.get(item_uid(item), date) == date]
    if len(fresh) < len(items):
        LOG.info(
            "dropped %d items already shown on previous days", len(items) - len(fresh)
        )

    # 2a. F5 keyword rules: mute is a hard drop (beats always). Over-broad rules
    # (swallowing most of the day) escalate to WARN; muting EVERYTHING renders a
    # visible note and exits 0 — an intentional empty digest is not degraded.
    fresh, muted = apply_mute(fresh, config)
    if muted:
        log_mute_summary(len(muted), len(fresh), [item.title for item, _ in muted])
    if not fresh and muted:
        LOG.warning("interests.mute dropped every fresh item today (%d)", len(muted))
        notice = (
            "interests.mute đã lọc mất toàn bộ mục hôm nay — kiểm tra lại danh sách "
            f"mute ({len(muted)} mục bị bỏ)."
        )
        html = render_digest(
            [],
            date=date,
            mode="empty",
            overview=heuristic_overview([], config),
            overview_label=overview_label(config),
            degraded=bool(failed),
            sources_failed=failed,
            model_name=config.llm.model,
            template=config.template_path,
            notice=notice,
            digest_data=build_digest_data([], [], date),
        )
        digest_path = write_digest(html, config.output_dir, date)
        days[date] = {
            "notified": False,
            "digest_path": str(digest_path),
            "mode": "empty",
            "sources_failed": failed,
            "item_count": 0,
        }
        save_json(config.state_path, state)
        return RunResult(
            digest_path=digest_path,
            mode="empty",
            degraded=bool(failed),
            sources_failed=failed,
            exit_code=0,
            message="muted everything today",
        )

    # 2c. F1 feedback: aggregate recent signals (ratings within the window,
    # saves pinned until unsave). ANY failure degrades to "no feedback" — never
    # blocks delivery.
    feedback_agg = FeedbackAggregate()
    adjustments: dict[str, float] = {}
    try:
        feedback_agg = aggregate(
            read_feedback(config.feedback_path), date, config.feedback.window_days
        )
        adjustments = topic_adjustments(feedback_agg, config.interests.topics)
    except Exception as exc:  # noqa: BLE001 — quality layer only
        LOG.warning(
            "feedback unavailable (%s: %s); continuing without it",
            type(exc).__name__,
            exc,
        )

    pool = balanced_pool(fresh, config, config.llm.max_pool, adjustments)

    # 2b. Citation enrichment (OpenAlex, keyless, one batched request): gives the
    # editor LLM — and the heuristic fallback — citation evidence per paper.
    # Cosmetic signal: failures keep the pool unchanged.
    pool = enrich_citations(pool, config)

    # 3. Rank (editor LLM with heuristic fallback). The reader_context block
    # carries the F4 profile + recent feedback signals; any failure building it
    # degrades to an empty block — never blocks delivery.
    reader_context = ""
    try:
        reader_context = reader_context_block(
            feedback_agg, load_profile(config), config.feedback.max_prompt_titles
        )
    except Exception as exc:  # noqa: BLE001 — quality layer only
        LOG.warning(
            "profile context unavailable (%s: %s); continuing without it",
            type(exc).__name__,
            exc,
        )
    ranked, mode = select(pool, llm_client, config, reader_context, adjustments)
    degraded = bool(failed) or mode != "llm"

    # 3b. Summarize (writer LLM): per-item summaries + the day OVERVIEW (one batched
    # call). Cosmetic quality step — failure keeps the raw abstracts and falls back
    # to the mechanical overview; never affects delivery or the exit code.
    overview = ""
    if config.llm.summarize and summary_client is not None:
        ranked, overview = summarize_with_llm(
            ranked, summary_client.chat, config, reader_context
        )
    if not overview:
        overview = heuristic_overview(ranked, config)  # always have something

    # 3c. "Nhìn lại": pinned saves (cap + overflow note), minus any uid that is
    # already in today's ranked (the fresher in-section card wins).
    pinned = pinned_items(feedback_agg, config.feedback.saved_cap)
    pinned_overflow = max(0, len(feedback_agg.saved) - len(pinned))
    ranked_uids = {r.item.id for r in ranked}
    pinned = [entry for entry in pinned if entry.get("uid") not in ranked_uids]

    # 3d. Optional real article images for hero + section leads. Best-effort:
    # failures only remove images; the LLM review uses the same app model.
    media_chat = None
    if config.media.enabled and config.media.llm_review:
        vision_client = summary_client or llm_client
        media_chat = vision_client.chat if vision_client else None
    images = collect_images(ranked, config, chat=media_chat)

    # 4. Render + archive atomically. The digest_data blob embeds the item
    # snapshots + date so popup-process features (feedback, ask) are self-pairing.
    html = render_digest(
        ranked,
        date=date,
        mode=mode,
        overview=overview,
        overview_label=overview_label(config),
        degraded=degraded,
        sources_failed=failed,
        model_name=config.llm.model,
        template=config.template_path,
        pinned=pinned,
        pinned_overflow=pinned_overflow,
        digest_data=build_digest_data(ranked, pinned, date),
        images=images,
        source_names=labels_for(config),
    )
    digest_path = write_digest(html, config.output_dir, date)

    # 5. Two-phase state: persisted as notified=false right after the digest exists
    entry = {
        "notified": False,
        "digest_path": str(digest_path),
        "mode": mode,
        "sources_failed": failed,
        "item_count": len(ranked),
    }
    days[date] = entry
    for ranked_item in ranked:
        seen[item_uid(ranked_item.item)] = date
    state["seen"] = _prune_seen(seen, date, config.state.seen_days)
    save_json(config.state_path, state)

    # 6. Notify; only flip to notified=true on success.
    # The desktop popup window is the primary delivery: it opens even if the toast
    # fails, and runs detached so it outlives this (time-limited) scheduled process.
    exit_code = 0 if not degraded else 1
    if notify_enabled:
        if config.notify.popup:
            spawn_popup_detached(digest_path)
        try:
            counts = {
                section: sum(1 for r in ranked if r.section == section)
                for section in SECTIONS
            }
            notify_fn(counts, digest_path, config.notify)
            entry["notified"] = True
            save_json(config.state_path, state)
        except Exception as exc:  # noqa: BLE001 — any toast failure must not kill the run
            LOG.error("notification failed: %s: %s", type(exc).__name__, exc)
            exit_code = 1
            degraded = True

    return RunResult(
        digest_path=digest_path,
        mode=mode,
        degraded=degraded,
        sources_failed=failed,
        item_count=len(ranked),
        exit_code=exit_code,
    )
