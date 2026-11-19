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
import re
import threading
import time

from daily_digest.config import Config
from daily_digest.feedback import (
    ACTIONS,
    aggregate,
    append_feedback,
    read_feedback,
)
from daily_digest.normalize import safe_href
from daily_digest.util import LOG

REFRESH_COOLDOWN_SECONDS = 60.0

_BLOB_RE = re.compile(
    r'<script[^>]*\bid="digest-data"[^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)


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
    ) -> None:
        self.config = config
        self.date = str(digest_data.get("date", ""))
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
            for entry in aggregate_now.saved.values():
                snapshot = dict(entry)
                snapshot["href"] = safe_href(str(snapshot.get("url", "")))
                items.append(snapshot)
            items.reverse()
            return {"ok": True, "items": items}
        except Exception as exc:  # noqa: BLE001 — Promise must never reject
            LOG.error("saved_items failed: %s: %s", type(exc).__name__, exc)
            return {"ok": False, "items": [], "error": str(exc)}

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
                spawned = spawn(["-m", "daily_digest", "run", "--force", "--new-only"])
                if not spawned:
                    return {"ok": False, "error": "spawn failed"}
                self._last_refresh = now
                return {"ok": True, "spawned": True}
        except Exception as exc:  # noqa: BLE001 — Promise must never reject
            LOG.error("refresh failed: %s: %s", type(exc).__name__, exc)
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
                return "Không tìm thấy mục này (digest cũ?)"
            question = (question or "").strip()
            if not question:
                return "Bạn chưa nhập câu hỏi."
            from daily_digest.ask import answer_question

            client = self._get_ask_chat()
            if client is None:
                chat_fn = None
            elif hasattr(client, "chat"):  # an LlmClient
                chat_fn = client.chat
            else:  # a plain callable (tests / custom factories)
                chat_fn = client
            return answer_question(snapshot, question, chat_fn, self._get_ask_profile())
        except Exception as exc:  # noqa: BLE001 — Promise must never reject
            LOG.error("ask failed: %s: %s", type(exc).__name__, exc)
            return f"Chưa hỏi được lúc này ({type(exc).__name__}). Thử lại sau nhé."
