"""Bridge between the digest HTML and the pywebview popup process.

The digest HTML carries its own data: a JSON blob in
<script type="application/json" id="digest-data">…</script> (rendered via Jinja
|tojson, which escapes < > & ' so the blob can never break out of the tag).
The popup process reads the WHOLE html file anyway, so the artifact is
self-pairing — works for latest.html and archived digests alike, and is inert
in browsers.

No webview imports here: everything is plain Python and unit-testable.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time

from daily_digest.backup import backup_digest
from daily_digest.config import Config
from daily_digest.digest_size import (
    DEFAULT_DIGEST_SIZE,
    MAX_DIGEST_SIZE,
    MIN_DIGEST_SIZE,
    DigestSizeError,
    clear_digest_size,
    clear_language,
    effective_max,
    load_preferences,
    normalize_digest_size,
    resolve_digest_size,
    save_digest_size,
    save_preferences,
    stored_digest_size,
)
from daily_digest.feedback import (
    ACTIONS,
    aggregate,
    append_feedback,
    read_feedback,
)
from daily_digest.i18n import (
    LOCALE_LABEL,
    SUPPORTED_LOCALES,
    LocaleError,
    normalize_locale,
    require_locale,
    resolve_locale,
    t,
)
from daily_digest.normalize import safe_href
from daily_digest.source_labels import labels_for
from daily_digest.util import LOG, today_str

REFRESH_COOLDOWN_SECONDS = 60.0

_BLOB_RE = re.compile(
    r'<script[^>]*\bid="digest-data"[^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)
_LANG_RE = re.compile(
    r'<html[^>]*\blang=["\']([^"\']+)["\']',
    re.IGNORECASE,
)


def extract_locale(html_text: str) -> str | None:
    """Read the baked locale from a digest's <html lang> attribute."""
    match = _LANG_RE.search(html_text)
    return normalize_locale(match.group(1)) if match else None


def extract_digest_data(html_text: str) -> dict:
    """Pull the uid->item data blob out of a digest HTML. Tolerant:
    returns {} for old digests (no blob), corrupt JSON, or non-dict payloads."""
    match = _BLOB_RE.search(html_text)
    if not match:
        return {}
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


class DigestBridge:
    """The pywebview js_api object. Every method MUST be exception-proof: a
    Python exception rejects the JS Promise (pywebview 6.x), so failures come
    back as {"ok": False} / polite strings instead."""

    def __init__(
        self,
        config: Config,
        digest_data: dict,
        chat_factory=None,
        spawn_fn=None,
        locale: str | None = None,
    ) -> None:
        self.config = config
        self.date = str(digest_data.get("date", ""))
        self.locale = normalize_locale(locale) or "vi"
        self.items: dict[str, dict] = dict(digest_data.get("items", {}))
        self.pinned: dict[str, dict] = {
            str(entry.get("uid", "")): entry
            for entry in digest_data.get("pinned", [])
            if isinstance(entry, dict) and entry.get("uid")
        }
        self._lock = threading.Lock()  # pywebview calls arrive on their own threads
        self._chat_factory = chat_factory  # None -> daily_digest.ask.build_popup_llm
        self._ask_chat = None
        self._ask_ready = False
        self._ask_profile: str | None = None
        self._spawn_fn = spawn_fn  # test seam: callable(args) -> bool
        self._last_refresh = 0.0

    def _snapshot_for(self, uid: str) -> dict | None:
        entry = self.items.get(uid) or self.pinned.get(uid)
        if isinstance(entry, dict):
            return dict(entry)
        return self._live_saved_snapshot(uid)

    def _live_saved_snapshot(self, uid: str) -> dict | None:
        """Resolve a save that is no longer in today's blob (older than the
        rail cap), so unsave/ask still work for it."""
        try:
            aggregate_now = aggregate(
                read_feedback(self.config.feedback_path),
                self.date or "",
                self.config.feedback.window_days,
            )
            entry = aggregate_now.saved.get(uid)
            return dict(entry) if isinstance(entry, dict) else None
        except Exception:  # noqa: BLE001 — bridge must never raise
            return None

    def toggle_save(self, uid: str) -> dict:
        """Save an item, or unsave it when it is already saved.

        This is the Lưu button's toggle: one button does both directions, so an
        accidental save can be undone with the same click. Never raises.
        """
        try:
            if not self.date:
                return {"ok": False, "error": "digest carries no date"}
            with self._lock:
                signals = read_feedback(self.config.feedback_path)
                aggregate_now = aggregate(
                    signals, self.date, self.config.feedback.window_days
                )
                if uid in aggregate_now.saved:
                    snapshot = dict(aggregate_now.saved[uid])
                    action = "unsave"
                else:
                    snapshot = self._snapshot_for(uid)
                    action = "save"
                if snapshot is None:
                    return {"ok": False, "error": "unknown item (old digest?)"}
                append_feedback(
                    self.config.feedback_path, uid, action, self.date, snapshot
                )
            LOG.info("feedback: toggle_save %s -> %s", uid, action)
            return {
                "ok": True,
                "uid": uid,
                "action": action,
                "saved": action == "save",
            }
        except Exception as exc:  # noqa: BLE001 — Promise must never reject
            LOG.error("toggle_save failed: %s: %s", type(exc).__name__, exc)
            return {"ok": False, "error": str(exc)}

    def ratings(self) -> dict:
        """Current like/dislike state per uid, so the popup can mark buttons."""
        try:
            aggregate_now = aggregate(
                read_feedback(self.config.feedback_path),
                self.date or "",
                self.config.feedback.window_days,
            )
            return {"ok": True, "ratings": dict(aggregate_now.ratings)}
        except Exception as exc:  # noqa: BLE001 — Promise must never reject
            LOG.error("ratings failed: %s: %s", type(exc).__name__, exc)
            return {"ok": False, "ratings": {}, "error": str(exc)}

    def saved_items(self) -> dict:
        """Every currently-saved article, read live from feedback.jsonl.

        Returns hrefs sanitized in Python (never raw URLs) so the modal JS can
        safely assign them to an anchor. Newest save first. Never raises.
        """
        try:
            aggregate_now = aggregate(
                read_feedback(self.config.feedback_path),
                self.date or "",
                self.config.feedback.window_days,
            )
            items: list[dict] = []
            labels = labels_for(self.config)
            for entry in aggregate_now.saved.values():
                snapshot = dict(entry)
                snapshot["href"] = safe_href(str(snapshot.get("url", "")))
                source = str(snapshot.get("source", ""))
                snapshot["source_label"] = labels.get(source, source)
                items.append(snapshot)
            items.reverse()
            return {"ok": True, "items": items}
        except Exception as exc:  # noqa: BLE001 — Promise must never reject
            LOG.error("saved_items failed: %s: %s", type(exc).__name__, exc)
            return {"ok": False, "items": [], "error": str(exc)}

    def undo_unsave(self, uid: str) -> dict:
        """Restore the most recent unsave for `uid` from its captured snapshot.

        The unsave signal in feedback.jsonl already carries the saved item's
        snapshot, so this works even if the item is no longer in today's blob.
        Never raises (bridge contract).
        """
        try:
            if not self.date:
                return {"ok": False, "error": "digest carries no date"}
            with self._lock:
                signals = read_feedback(self.config.feedback_path)
                aggregate_now = aggregate(
                    signals, self.date, self.config.feedback.window_days
                )
                if uid in aggregate_now.saved:
                    return {"ok": False, "error": "item is already saved"}
                previous = next(
                    (
                        signal
                        for signal in reversed(signals)
                        if signal.uid == uid
                        and signal.action == "unsave"
                        and signal.snapshot
                    ),
                    None,
                )
                if previous is None:
                    return {"ok": False, "error": "nothing to undo"}
                append_feedback(
                    self.config.feedback_path,
                    uid,
                    "save",
                    self.date,
                    previous.snapshot,
                )
            LOG.info("feedback: undo unsave %s", uid)
            return {"ok": True, "uid": uid}
        except Exception as exc:  # noqa: BLE001 — Promise must never reject
            LOG.error("undo_unsave failed: %s: %s", type(exc).__name__, exc)
            return {"ok": False, "error": str(exc)}

    def refresh(self) -> dict:
        """Spawn a detached `run --force --new-only`; 60s single-flight guard."""
        try:
            with self._lock:
                now = time.monotonic()
                if now - self._last_refresh < REFRESH_COOLDOWN_SECONDS:
                    return {"ok": False, "error": "already refreshing"}
                spawn = self._spawn_fn
                if spawn is None:
                    from daily_digest.popup import spawn_cli

                    spawn = spawn_cli
                # spawn_cli prepends the interpreter and `-m daily_digest`.
                spawned = spawn(["run", "--force", "--new-only"])
                if not spawned:
                    return {"ok": False, "error": "spawn failed"}
                self._last_refresh = now
                return {"ok": True, "spawned": True}
        except Exception as exc:  # noqa: BLE001 — Promise must never reject
            LOG.error("refresh failed: %s: %s", type(exc).__name__, exc)
            return {"ok": False, "error": str(exc)}

    def settings(self) -> dict:
        """Return size + language controls for the current digest."""
        try:
            archived = not self.date or self.date != today_str()
            preferences = load_preferences(self.config.preferences_path)
            cap = effective_max(self.config)
            stored_language = normalize_locale(preferences.get("language"))
            return {
                "ok": True,
                "size": resolve_digest_size(self.config, preferences),
                "default": DEFAULT_DIGEST_SIZE,
                "min": MIN_DIGEST_SIZE,
                "max": cap,
                "stored": stored_digest_size(preferences),
                "current": len(self.items),
                "can_change": not archived,
                "archived": archived,
                "has_key": bool(os.environ.get(self.config.llm.api_key_env)),
                "language": self.locale,
                "stored_language": stored_language,
                "languages": [
                    {"code": code, "label": LOCALE_LABEL[code]}
                    for code in SUPPORTED_LOCALES
                ],
            }
        except Exception as exc:  # noqa: BLE001 — bridge must never raise
            LOG.error("settings failed: %s: %s", type(exc).__name__, exc)
            return {"ok": False, "error": str(exc), "can_change": False}

    def apply_settings(self, size: int, language: str) -> dict:
        """Validate, back up, save size + language once, then spawn one rebuild."""
        saved = False
        try:
            if not self.date or self.date != today_str():
                return {
                    "ok": False,
                    "saved": False,
                    "spawned": False,
                    "archived": True,
                    "error": "archived digest",
                }
            try:
                normalized = normalize_digest_size(size)
            except DigestSizeError as exc:
                return {
                    "ok": False,
                    "saved": False,
                    "spawned": False,
                    "error": str(exc),
                }
            cap = effective_max(self.config)
            if normalized > cap:
                return {
                    "ok": False,
                    "saved": False,
                    "spawned": False,
                    "error": f"size must be <= {cap}",
                }
            try:
                locale = require_locale(language)
            except LocaleError as exc:
                return {
                    "ok": False,
                    "saved": False,
                    "spawned": False,
                    "error": str(exc),
                }

            with self._lock:
                preferences = load_preferences(self.config.preferences_path)
                previous_size = resolve_digest_size(self.config, preferences)
                previous_locale = resolve_locale(self.config, preferences)
                source = self.config.output_dir / f"digest-{self.date}.html"
                try:
                    backup_digest(source, self.config.output_dir)
                except OSError as exc:
                    LOG.error("settings backup failed: %s", exc)
                    return {
                        "ok": False,
                        "saved": False,
                        "spawned": False,
                        "error": f"backup failed: {exc}",
                    }
                save_preferences(
                    self.config.preferences_path,
                    digest_size=normalized,
                    language=locale,
                )
                saved = True
                changed = (
                    normalized != len(self.items)
                    or locale != self.locale
                    or normalized != previous_size
                    or locale != previous_locale
                )
                if not changed:
                    return {
                        "ok": True,
                        "saved": True,
                        "spawned": False,
                        "size": normalized,
                        "language": locale,
                        "message": "already using these settings",
                    }
                now = time.monotonic()
                if now - self._last_refresh < REFRESH_COOLDOWN_SECONDS:
                    return {
                        "ok": False,
                        "saved": True,
                        "spawned": False,
                        "size": normalized,
                        "language": locale,
                        "error": "already refreshing",
                    }
                spawn = self._spawn_fn
                if spawn is None:
                    from daily_digest.popup import spawn_cli

                    spawn = spawn_cli
                spawned = spawn(
                    [
                        "run",
                        "--force",
                        "--count",
                        str(normalized),
                        "--lang",
                        locale,
                    ]
                )
                if not spawned:
                    return {
                        "ok": False,
                        "saved": True,
                        "spawned": False,
                        "size": normalized,
                        "language": locale,
                        "error": "spawn failed; settings saved for the next run",
                    }
                self._last_refresh = now
                return {
                    "ok": True,
                    "saved": True,
                    "spawned": True,
                    "size": normalized,
                    "language": locale,
                }
        except Exception as exc:  # noqa: BLE001 — bridge must never raise
            LOG.error("apply_settings failed: %s: %s", type(exc).__name__, exc)
            return {
                "ok": False,
                "saved": saved,
                "spawned": False,
                "error": str(exc),
            }

    def reset_settings(self) -> dict:
        """Remove stored size + language preferences."""
        try:
            clear_digest_size(self.config.preferences_path)
            clear_language(self.config.preferences_path)
            preferences = load_preferences(self.config.preferences_path)
            return {
                "ok": True,
                "size": resolve_digest_size(self.config, preferences),
                "stored": stored_digest_size(preferences),
                "language": self.locale,
                "stored_language": None,
            }
        except Exception as exc:  # noqa: BLE001 — bridge must never raise
            LOG.error("reset_settings failed: %s: %s", type(exc).__name__, exc)
            return {"ok": False, "error": str(exc)}

    def digest_size(self) -> dict:
        """Return the effective size and whether this digest can change it."""
        try:
            archived = self.date != today_str()
            preferences = load_preferences(self.config.preferences_path)
            cap = effective_max(self.config)
            return {
                "ok": True,
                "size": resolve_digest_size(self.config, preferences),
                "default": DEFAULT_DIGEST_SIZE,
                "min": MIN_DIGEST_SIZE,
                "max": cap,
                "stored": stored_digest_size(preferences),
                "current": len(self.items),
                "can_change": not archived,
                "archived": archived,
                "has_key": bool(os.environ.get(self.config.llm.api_key_env)),
            }
        except Exception as exc:  # noqa: BLE001  Ebridge must never raise
            LOG.error("digest_size failed: %s: %s", type(exc).__name__, exc)
            return {"ok": False, "error": str(exc), "can_change": False}

    def set_digest_size(self, size: int) -> dict:
        """Persist a size preference and spawn a detached rebuild."""
        saved = False
        try:
            if not self.date or self.date != today_str():
                return {
                    "ok": False,
                    "saved": False,
                    "spawned": False,
                    "archived": True,
                    "error": "archived digest",
                }
            try:
                normalized = normalize_digest_size(size)
            except DigestSizeError as exc:
                return {
                    "ok": False,
                    "saved": False,
                    "spawned": False,
                    "error": str(exc),
                }
            cap = effective_max(self.config)
            if normalized > cap:
                return {
                    "ok": False,
                    "saved": False,
                    "spawned": False,
                    "error": f"size must be <= {cap}",
                }

            with self._lock:
                previous = resolve_digest_size(
                    self.config, load_preferences(self.config.preferences_path)
                )
                save_digest_size(self.config.preferences_path, normalized)
                saved = True
                current = len(self.items)
                if normalized == previous and normalized == current:
                    return {
                        "ok": True,
                        "saved": True,
                        "spawned": False,
                        "size": normalized,
                        "message": "already using this size",
                    }
                if normalized == current:
                    return {
                        "ok": True,
                        "saved": True,
                        "spawned": False,
                        "size": normalized,
                        "message": "preference saved",
                    }
                now = time.monotonic()
                if now - self._last_refresh < REFRESH_COOLDOWN_SECONDS:
                    return {
                        "ok": False,
                        "saved": True,
                        "spawned": False,
                        "size": normalized,
                        "error": "already refreshing",
                    }
                spawn = self._spawn_fn
                if spawn is None:
                    from daily_digest.popup import spawn_cli

                    spawn = spawn_cli
                spawned = spawn(["run", "--force", "--count", str(normalized)])
                if not spawned:
                    return {
                        "ok": False,
                        "saved": True,
                        "spawned": False,
                        "size": normalized,
                        "error": "spawn failed; preference saved for the next run",
                    }
                self._last_refresh = now
                return {
                    "ok": True,
                    "saved": True,
                    "spawned": True,
                    "size": normalized,
                }
        except Exception as exc:  # noqa: BLE001  Ebridge must never raise
            LOG.error("set_digest_size failed: %s: %s", type(exc).__name__, exc)
            return {
                "ok": False,
                "saved": saved,
                "spawned": False,
                "error": str(exc),
            }

    def reset_digest_size(self) -> dict:
        """Remove the stored preference; the next run uses config/default."""
        try:
            clear_digest_size(self.config.preferences_path)
            preferences = load_preferences(self.config.preferences_path)
            return {
                "ok": True,
                "size": resolve_digest_size(self.config, preferences),
                "stored": stored_digest_size(preferences),
            }
        except Exception as exc:  # noqa: BLE001  Ebridge must never raise
            LOG.error("reset_digest_size failed: %s: %s", type(exc).__name__, exc)
            return {"ok": False, "error": str(exc)}

    def _get_ask_chat(self):
        """Lazily build the ask LLM client on the FIRST question — the daily run
        is long gone by then, eliminating the spawn-vs-save state.json race."""
        if not self._ask_ready:
            factory = self._chat_factory
            if factory is None:
                from daily_digest.ask import build_popup_llm

                factory = build_popup_llm
            self._ask_chat = factory(self.config)
            self._ask_ready = True
        return self._ask_chat

    def _get_ask_profile(self) -> str:
        if self._ask_profile is None:
            from daily_digest.profile import load_profile

            try:
                self._ask_profile = load_profile(self.config)
            except Exception:  # noqa: BLE001 — profile is optional context
                self._ask_profile = ""
        return self._ask_profile

    def feedback(self, uid: str, action: str) -> dict:
        try:
            if action not in ACTIONS:
                return {"ok": False, "error": f"unknown action {action!r}"}
            snapshot = self._snapshot_for(uid)
            if snapshot is None:
                return {"ok": False, "error": "unknown item (old digest?)"}
            if not self.date:
                return {"ok": False, "error": "digest carries no date"}
            append_feedback(self.config.feedback_path, uid, action, self.date, snapshot)
            LOG.info("feedback: %s %s", action, uid)
            return {"ok": True, "action": action, "uid": uid}
        except Exception as exc:  # noqa: BLE001 — Promise must never reject
            LOG.error("feedback failed: %s: %s", type(exc).__name__, exc)
            return {"ok": False, "error": str(exc)}

    def ask(self, uid: str, question: str) -> str:
        try:
            snapshot = self._snapshot_for(uid)
            if snapshot is None:
                return t(self.locale, "ask_unknown_item")
            question = (question or "").strip()
            if not question:
                return t(self.locale, "ask_empty")
            from daily_digest.ask import answer_question

            client = self._get_ask_chat()
            if client is None:
                chat_fn = None
            elif hasattr(client, "chat"):  # an LlmClient
                chat_fn = client.chat
            else:  # a plain callable (tests / custom factories)
                chat_fn = client
            return answer_question(
                snapshot,
                question,
                chat_fn,
                self._get_ask_profile(),
                self.locale,
            )
        except Exception as exc:  # noqa: BLE001 — Promise must never reject
            LOG.error("ask failed: %s: %s", type(exc).__name__, exc)
            return t(self.locale, "ask_error")
