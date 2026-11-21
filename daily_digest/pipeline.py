"""The daily pipeline: fetch -> merge/dedupe -> seen-set -> rank -> render -> notify -> state.

Exit codes: 0 clean · 1 degraded (partial sources, heuristic mode, notify failure,
zero items from healthy sources) · 2 fatal (config, all sources failed).
"""

from __future__ import annotations

import shutil
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

import httpx

from daily_digest.config import Config
from daily_digest.article import hydrate_hn_links
from daily_digest.backup import backup_digest
from daily_digest.digest_size import load_preferences, resolve_digest_size
from daily_digest.edition import Edition, render_edition, save_edition, with_artifact
from daily_digest.enrich import enrich_citations
from daily_digest.feedback import (
    FeedbackAggregate,
    aggregate,
    pinned_items,
    read_feedback,
    reader_context_block,
    topic_adjustments,
)
from daily_digest.i18n import resolve_locale, t
from daily_digest.model import Item, RunResult, SECTIONS
from daily_digest.normalize import item_uid
from daily_digest.notify import notify
from daily_digest.overview import (
    ensure_coverage,
    heuristic_overview_points,
    parse_overview,
)
from daily_digest.popup import spawn_popup_detached
from daily_digest.profile import load_profile
from daily_digest.ranking import select
from daily_digest.ranking.heuristic import (
    balanced_pool,
    heuristic_order,
    heuristic_overview,
)
from daily_digest.media import collect_images
from daily_digest.ranking.llm import LlmClient, summarize_with_llm, writer_deadline
from daily_digest.render import write_digest
from daily_digest.rules import apply_mute, log_mute_summary
from daily_digest.sources import SourceError, enabled_sources, fetch_all
from daily_digest.util import LOG, load_json, save_json, today_str


RUN_BUDGET_SECONDS = 12 * 60


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


def _backup_morning_digest(output_dir: Path, date: str) -> Path | None:
    """Copy the same-day digest to the next free morning-backup name."""
    source = output_dir / f"digest-{date}.html"
    try:
        return backup_digest(source, output_dir)
    except OSError as exc:
        LOG.warning("morning digest backup failed: %s", exc)
        return None


def _persist_edition(
    edition: Edition, html: str, path: Path, output_dir: Path
) -> Edition:
    """Attach the actual artifact metadata and persist the sidecar (best-effort)."""
    edition = with_artifact(edition, path, html, output_dir)
    try:
        save_edition(edition, output_dir)
    except Exception as exc:  # noqa: BLE001 — snapshots must not break delivery
        LOG.warning("edition snapshot failed: %s: %s", type(exc).__name__, exc)
    return edition


def run_day(
    config: Config,
    date: str | None = None,
    *,
    http: httpx.Client | None = None,
    llm_client: LlmClient | None = None,
    force: bool = False,
    new_only: bool = False,
    notify_enabled: bool = True,
    notify_fn: Callable[..., None] = notify,
    summary_client: LlmClient | None = None,
    target: int | None = None,
    language: str | None = None,
) -> RunResult:
    date = date or today_str()
    state = load_json(config.state_path)
    preferences = load_preferences(config.preferences_path)
    target = resolve_digest_size(config, preferences, target)
    locale = resolve_locale(config, preferences, language)
    deadline = time.monotonic() + RUN_BUDGET_SECONDS
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

    # 2. Merge duplicates, then drop items already shown on previous days.
    # `new_only` is stricter: it also drops same-day items already shown in the
    # morning digest (the manual "Tìm bài mới" refresh).
    items = merge_items(items)
    seen: dict[str, str] = state.get("seen", {})
    if new_only:
        fresh = [item for item in items if item_uid(item) not in seen]
    else:
        fresh = [item for item in items if seen.get(item_uid(item), date) == date]
    if len(fresh) < len(items):
        LOG.info(
            "dropped %d items already shown%s",
            len(items) - len(fresh),
            " (new-only)" if new_only else " on previous days",
        )

    # Nothing new since the last digest: leave state, artifacts and notifications
    # untouched. A failed source is NOT "nothing new" — it keeps the degraded exit.
    if new_only and not fresh:
        LOG.info("new-only: no unseen items — leaving the current digest untouched")
        return RunResult(
            mode="nothing-new",
            degraded=bool(failed),
            sources_failed=failed,
            exit_code=1 if failed else 0,
            message="no new items since the last digest",
        )

    # 2a. F5 keyword rules: mute is a hard drop (beats always). Over-broad rules
    # (swallowing most of the day) escalate to WARN; muting EVERYTHING renders a
    # visible note and exits 0 — an intentional empty digest is not degraded.
    fresh, muted = apply_mute(fresh, config)
    if muted:
        log_mute_summary(len(muted), len(fresh), [item.title for item, _ in muted])
    if not fresh and muted:
        LOG.warning("interests.mute dropped every fresh item today (%d)", len(muted))
        notice = t(locale, "notice_muted_all").format(n=len(muted))
        edition = Edition(
            date=date,
            locale=locale,
            ranked=(),
            mode="empty",
            model_name=config.llm.model,
            degraded=bool(failed),
            sources_failed=tuple(failed),
            overview=heuristic_overview([], config, locale),
            overview_points=(),
            notice_text=notice,
        )
        html = render_edition(edition, config)
        if new_only or force:
            _backup_morning_digest(config.output_dir, date)
        digest_path = write_digest(html, config.output_dir, date)
        _persist_edition(edition, html, digest_path, config.output_dir)
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

    # 2b. HN link hydration: link posts carry no Algolia story_text, so the
    # editor pool and the writer would otherwise see title-only items.
    # Best-effort quality step — failures never degrade the run.
    if config.sources.hn.hydrate:
        fresh = hydrate_hn_links(fresh, config)

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

    # 2d. New-only backfill: when fewer than top_n unseen items exist, top up
    # from notable items shown on PREVIOUS days only (never today's morning
    # digest). Muted topics stay muted; heuristic order keeps the strongest.
    if new_only and len(fresh) < target:
        previous = [
            item
            for item in items
            if (shown := seen.get(item_uid(item))) and shown != date
        ]
        previous, _ = apply_mute(previous, config)
        need = target - len(fresh)
        backfill = heuristic_order(previous, config, adjustments, locale)[:need]
        if backfill:
            fresh = merge_items([*fresh, *backfill])
            LOG.info(
                "new-only: backfilled %d notable previous-day items (now %d/%d)",
                len(backfill),
                len(fresh),
                target,
            )

    pool = balanced_pool(fresh, config, config.llm.max_pool, adjustments, locale)

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
    ranked, mode = select(
        pool,
        llm_client,
        config,
        reader_context,
        adjustments,
        target=target,
        locale=locale,
    )
    if len(ranked) < target:
        LOG.info(
            "digest size: requested %d, selected %d (candidate pool short)",
            target,
            len(ranked),
        )
    degraded = bool(failed) or mode != "llm"

    # 3b. Summarize (writer LLM): per-item summaries + the day OVERVIEW (one batched
    # call). Cosmetic quality step — failure keeps the raw abstracts and falls back
    # to the mechanical overview; never affects delivery or the exit code.
    overview = ""
    overview_points = ()
    if config.llm.summarize and summary_client is not None:
        if time.monotonic() < deadline:
            with writer_deadline(deadline):
                ranked, overview = summarize_with_llm(
                    ranked,
                    summary_client.chat,
                    config,
                    reader_context,
                    locale,
                )
        else:
            LOG.warning("run budget exceeded before writer; keeping raw abstracts")
    if overview:
        overview_points = ensure_coverage(
            parse_overview(overview, ranked, locale), ranked, locale
        )
    if not overview_points:
        if not overview:
            overview = heuristic_overview(
                ranked, config, locale
            )  # always have something
        overview_points = heuristic_overview_points(ranked, config, locale)
    writer_notice_text = ""
    writer_notice_key = ""
    if config.llm.writer_v2 and ranked:
        covered = sum(1 for item in ranked if item.llm_summary)
        if covered < len(ranked):
            degraded = True
            writer_notice_key = "writer_partial"
            writer_notice_text = t(locale, writer_notice_key)
            LOG.warning(
                "writer v2 wrote %d/%d summaries; digest is degraded",
                covered,
                len(ranked),
            )

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
    edition = Edition(
        date=date,
        locale=locale,
        ranked=tuple(ranked),
        mode=mode,
        model_name=config.llm.model,
        degraded=degraded,
        sources_failed=tuple(failed),
        overview=overview,
        overview_points=tuple(overview_points),
        notice_text=writer_notice_text,
        notice_key=writer_notice_key,
        pinned=tuple(pinned),
        pinned_overflow=pinned_overflow,
        images=images,
    )
    html = render_edition(edition, config)
    if new_only or force or config.llm.writer_v2:
        _backup_morning_digest(config.output_dir, date)
    digest_path = write_digest(html, config.output_dir, date)
    _persist_edition(edition, html, digest_path, config.output_dir)

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
