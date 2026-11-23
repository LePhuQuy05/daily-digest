"""Localize an already-selected edition without fetching or re-ranking it."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import time
from pathlib import Path

from daily_digest.backup import backup_digest
from daily_digest.config import Config
from daily_digest.digest_size import load_preferences, save_preferences
from daily_digest.edition import (
    Edition,
    edition_from_legacy_html,
    extract_images_from_html,
    load_edition,
    localize_status_path,
    render_edition,
    save_edition,
    with_artifact,
)
from daily_digest.i18n import (
    PROMPT_LANGUAGE,
    fails_kana_gate,
    normalize_locale,
    t,
)
from daily_digest.lock import FileLock, LockError
from daily_digest.model import Notice, RankedItem, RunResult
from daily_digest.overview import (
    complete_section_briefs,
    ensure_coverage,
    heuristic_overview_points,
    parse_overview,
)
from daily_digest.ranking.heuristic import heuristic_overview, heuristic_why
from daily_digest.ranking.llm import (
    _extract_json,
    summarize_with_llm,
    write_section_briefs,
    writer_deadline,
)
from daily_digest.util import LOG, atomic_write_text, load_json, save_json, today_str
from daily_digest.render import write_digest

MAX_WHY = 140
MAX_WHY_JA = 80
WHY_INPUT_CHARS = 1200
WHY_INPUT_CHARS_JA = 400
LOCALIZE_BUDGET_SECONDS = 10 * 60

LOCALIZE_WHY_PROMPT = (
    "You localize an editor's one-line rationale for a daily tech digest. "
    "The reader's interests: {topics}.\n"
    "For every numbered item, rewrite the rationale in {language}. Preserve the "
    "original meaning and use the source abstract for grounding. Do not translate "
    "titles or URLs. Keep each rationale under {why_limit} characters. Use natural "
    "language; keep standard technical names in Latin script when appropriate.\n"
    "Respond with ONLY a JSON object, no markdown fences, in this shape:\n"
    '{{"items": [{{"id": <candidate number>, "why": "<localized rationale>"}}]}}'
)


def _chat(client):
    if client is None:
        return None
    return client.chat if hasattr(client, "chat") else client


def _fallback_whys(
    ranked: list[RankedItem], config: Config, locale: str
) -> list[RankedItem]:
    return [
        dataclasses.replace(
            item,
            why=heuristic_why(item.item, config, locale),
            llm_summary="",
        )
        for item in ranked
    ]


def localize_whys_with_llm(
    ranked: list[RankedItem],
    chat,
    config: Config,
    reader_context: str = "",
    locale: str = "vi",
) -> tuple[list[RankedItem], bool]:
    """Return localized why lines; bool is False when a deterministic fallback was used."""
    loc = normalize_locale(locale) or "vi"
    fallback = _fallback_whys(ranked, config, loc)
    if chat is None or not ranked:
        return fallback, not ranked
    why_limit = MAX_WHY_JA if loc == "ja" else MAX_WHY
    input_limit = WHY_INPUT_CHARS_JA if loc == "ja" else WHY_INPUT_CHARS
    lines = []
    for index, item in enumerate(ranked):
        description = " ".join(item.item.summary.split())[:input_limit]
        lines.append(
            f"[{index}] ({item.section}) {item.item.title}\n"
            f"    abstract: {description}\n"
            f"    old why: {item.why or '(none)'}"
        )
    system = LOCALIZE_WHY_PROMPT.format(
        topics=", ".join(config.interests.topics),
        language=PROMPT_LANGUAGE[loc],
        why_limit=why_limit,
    )
    messages: list[dict] = [
        {
            "role": "system",
            "content": system + ("\n" + reader_context if reader_context else ""),
        },
        {"role": "user", "content": "\n".join(lines)},
    ]

    def parse(text: str) -> dict[int, str]:
        payload = _extract_json(text)
        entries = payload.get("items", [])
        if not isinstance(entries, list):
            raise ValueError("'items' is not a list")
        result: dict[int, str] = {}
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            try:
                index = int(entry["id"])
            except (KeyError, TypeError, ValueError):
                continue
            if not 0 <= index < len(ranked):
                continue
            why = str(entry.get("why", "")).strip()[:why_limit]
            if not why:
                continue
            if fails_kana_gate(why, loc):
                continue
            result[index] = why
        if not result:
            raise ValueError("no valid localized why entries")
        return result

    text = chat(messages)
    try:
        whys = parse(text)
    except (ValueError, json.JSONDecodeError) as first_error:
        LOG.debug("localized why JSON invalid (%s); asking for one repair", first_error)
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
            whys = parse(chat(messages))
        except (ValueError, json.JSONDecodeError) as second_error:
            LOG.warning(
                "localized why failed: %s; using heuristic reasons", second_error
            )
            return fallback, False

    localized = []
    for index, item in enumerate(ranked):
        why = whys.get(index)
        localized.append(
            dataclasses.replace(
                item,
                why=why or heuristic_why(item.item, config, loc),
                llm_summary="",
            )
        )
    return localized, len(whys) == len(ranked)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _notice_line(notice: Notice, locale: str) -> str:
    """Localize one structured notice, falling back to its stored text."""
    if notice.key:
        rendered = t(locale, notice.key, **dict(notice.params))
        if rendered != notice.key:
            return rendered
    return notice.text


def _localize_edition_unlocked(
    config: Config,
    date: str,
    locale: str,
    *,
    editor_client=None,
    writer_client=None,
    expect_count: int | None = None,
    backup: bool = True,
    open_popup: bool = False,
    html_path: Path | None = None,
    reader_context: str = "",
) -> RunResult:
    """Localize today's edition in place, preserving its ordered item set."""
    loc = normalize_locale(locale)
    if loc is None:
        return RunResult(exit_code=2, message=f"unsupported locale: {locale!r}")
    if date != today_str():
        return RunResult(exit_code=2, message="archived digest is read-only")

    edition = load_edition(config.output_dir, date)
    path = html_path
    if path is None and edition is not None and edition.html_relpath:
        path = config.output_dir / edition.html_relpath
    if path is None:
        path = config.output_dir / f"digest-{date}.html"
    try:
        html_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return RunResult(exit_code=2, message=f"current digest unreadable: {exc}")

    if edition is not None and edition.html_sha256:
        if _sha256(html_text) != edition.html_sha256:
            return RunResult(
                exit_code=2, message="snapshot does not match current HTML"
            )
    elif edition is None:
        edition = edition_from_legacy_html(html_text, path, config, config.output_dir)
        if edition is None:
            return RunResult(
                exit_code=2, message="current digest cannot be reconstructed"
            )

    if expect_count is not None and len(edition.ranked) != expect_count:
        return RunResult(
            exit_code=2,
            message=f"edition has {len(edition.ranked)} items, expected {expect_count}",
        )

    if not edition.ranked and edition.mode == "empty":
        # Nothing to translate; still allow a target-locale chrome re-render.
        ranked: list[RankedItem] = []
    else:
        ranked = [
            dataclasses.replace(item, why="", llm_summary="") for item in edition.ranked
        ]

    # Source failures and heuristic mode survive localization because a
    # language switch cannot repair them. Writer/overview failures belong to
    # this run and are recomputed below.
    source_degraded = bool(edition.sources_failed) or edition.mode == "heuristic"
    localize_degraded = False
    localized, why_ok = localize_whys_with_llm(
        ranked, _chat(editor_client), config, reader_context, loc
    )
    localize_degraded = localize_degraded or not why_ok

    localize_deadline = time.monotonic() + LOCALIZE_BUDGET_SECONDS
    overview = ""
    if config.llm.summarize and _chat(writer_client) is not None and localized:
        with writer_deadline(localize_deadline):
            localized, overview = summarize_with_llm(
                localized, _chat(writer_client), config, reader_context, loc
            )
    if localized and not overview:
        localize_degraded = True
        overview = heuristic_overview(localized, config, loc)
    points = (
        ensure_coverage(parse_overview(overview, localized, loc), localized, loc)
        if localized
        else ()
    )
    if not points and localized:
        localize_degraded = True
        points = heuristic_overview_points(localized, config, loc)
    writer_attempted = (
        config.llm.summarize and _chat(writer_client) is not None and bool(localized)
    )
    writer_incomplete = False
    if localized and (
        not any(item.llm_summary for item in localized)
        or (
            (
                config.llm.writer_v2
                or (config.llm.auto_batch_long and len(localized) > 16)
            )
            and not all(item.llm_summary for item in localized)
        )
    ):
        localize_degraded = True
        writer_incomplete = writer_attempted

    section_briefs = ()
    if config.llm.section_briefs and localized:
        briefs = ()
        if config.llm.summarize and _chat(writer_client) is not None:
            brief_deadline = localize_deadline
            with writer_deadline(brief_deadline):
                briefs = write_section_briefs(
                    localized,
                    _chat(writer_client),
                    config,
                    reader_context=reader_context,
                    locale=loc,
                    deadline=brief_deadline,
                )
        section_briefs = complete_section_briefs(briefs, localized, config, loc)

    if backup:
        try:
            backup_digest(path, config.output_dir)
        except OSError as exc:
            return RunResult(exit_code=2, message=f"backup failed: {exc}")

    carried = [
        notice
        for notice in edition.notices
        if notice.key not in ("writer_partial", "localize_fallback")
    ]
    if (
        not carried
        and edition.notice_key
        and edition.notice_key
        not in (
            "writer_partial",
            "localize_fallback",
        )
    ):
        carried.append(
            Notice(
                key=edition.notice_key,
                params=dict(edition.notice_params),
                text=edition.notice_text,
            )
        )
    if localize_degraded:
        carried.append(
            Notice(key="localize_fallback", text=t(loc, "localize_fallback"))
        )
    if writer_incomplete:
        carried.append(Notice(key="writer_partial", text=t(loc, "writer_partial")))
    notice_text = " ".join(
        line for line in (_notice_line(notice, loc) for notice in carried) if line
    )
    notice_key = carried[0].key if len(carried) == 1 else ""
    notice_params = dict(carried[0].params) if len(carried) == 1 else {}
    images = extract_images_from_html(html_text)
    localized_edition = dataclasses.replace(
        edition,
        locale=loc,
        ranked=tuple(localized),
        overview=overview,
        overview_points=tuple(points),
        section_briefs=section_briefs,
        notices=tuple(carried),
        notice_text=notice_text,
        notice_key=notice_key,
        notice_params=notice_params,
        degraded=localize_degraded or source_degraded,
        images=images,
    )
    if date != today_str():
        return RunResult(exit_code=2, message="date changed during localization")
    html = render_edition(localized_edition, config)
    digest_path = write_digest(html, config.output_dir, date, preferred_path=path)
    localized_edition = with_artifact(
        localized_edition, digest_path, html, config.output_dir
    )
    try:
        save_edition(localized_edition, config.output_dir)
    except OSError as exc:
        LOG.warning("localized edition snapshot failed: %s", exc)

    state = load_json(config.state_path)
    days = state.setdefault("days", {})
    entry = days.setdefault(date, {})
    entry["digest_path"] = str(digest_path)
    save_json(config.state_path, state)

    if open_popup:
        from daily_digest.popup import spawn_popup_detached

        spawn_popup_detached(digest_path)
    return RunResult(
        digest_path=digest_path,
        mode="localized",
        degraded=localized_edition.degraded,
        sources_failed=list(localized_edition.sources_failed),
        item_count=len(localized),
        exit_code=1 if localized_edition.degraded else 0,
        message="localized current edition",
    )


def _write_localize_status(
    config: Config,
    date: str,
    state: str,
    message: str,
    locale: str,
    previous_language: str | None,
) -> None:
    try:
        path = localize_status_path(config.output_dir, date)
        payload = {
            "state": state,
            "date": date,
            "locale": locale,
            "previous_language": previous_language,
            "message": message,
        }
        atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))
    except Exception as exc:  # noqa: BLE001 — status is best-effort
        LOG.warning("localize status update failed: %s", exc)


def _restore_previous_language(
    config: Config, locale: str, previous_language: str | None
) -> None:
    if not previous_language:
        return
    try:
        current = normalize_locale(
            load_preferences(config.preferences_path).get("language")
        )
        if current == normalize_locale(locale):
            save_preferences(config.preferences_path, language=previous_language)
    except Exception as exc:  # noqa: BLE001 — bridge/CLI must not crash
        LOG.warning("language preference rollback failed: %s", exc)


def localize_edition(
    config: Config,
    date: str,
    locale: str,
    *,
    editor_client=None,
    writer_client=None,
    expect_count: int | None = None,
    backup: bool = True,
    open_popup: bool = False,
    html_path: Path | None = None,
    reader_context: str = "",
    rollback_language: str | None = None,
) -> RunResult:
    """Serialize the read-render-write transaction and roll back on failure."""
    _write_localize_status(
        config, date, "running", "localizing current edition", locale, rollback_language
    )
    lock = FileLock(config.output_dir / ".localize.lock")
    try:
        lock.acquire()
    except LockError as exc:
        _restore_previous_language(config, locale, rollback_language)
        _write_localize_status(
            config, date, "error", str(exc), locale, rollback_language
        )
        return RunResult(exit_code=2, message=str(exc))
    try:
        try:
            result = _localize_edition_unlocked(
                config,
                date,
                locale,
                editor_client=editor_client,
                writer_client=writer_client,
                expect_count=expect_count,
                backup=backup,
                open_popup=open_popup,
                html_path=html_path,
                reader_context=reader_context,
            )
        except Exception as exc:  # noqa: BLE001 — detached job must report
            LOG.exception("localize failed")
            _restore_previous_language(config, locale, rollback_language)
            _write_localize_status(
                config, date, "error", str(exc), locale, rollback_language
            )
            return RunResult(exit_code=2, message=str(exc))
        if result.exit_code == 2:
            _restore_previous_language(config, locale, rollback_language)
            state = "error"
        elif result.exit_code == 1:
            state = "degraded"
        else:
            state = "success"
        _write_localize_status(
            config,
            date,
            state,
            result.message or state,
            locale,
            rollback_language,
        )
        return result
    finally:
        lock.release()
