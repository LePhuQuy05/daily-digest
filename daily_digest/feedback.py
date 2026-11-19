"""F1 feedback persistence: an append-only JSONL log written by popup processes
and read (tolerantly) by the daily run.

Append atomicity (day-0 probe, 2026-11-19): on Windows, CRT 'a'-mode and even
os.open(O_APPEND)+os.write TEAR lines under concurrent writers (5 torn / 74 lost
of 1000). CreateFileW(FILE_APPEND_DATA) + a single WriteFile is atomic —
1000/1000 intact, including 12KB lines. POSIX O_APPEND is atomic by spec, so the
plain os.write path is kept there.

Aggregation uses TWO channels so toggles count once: `rating` (the LAST of
like/dislike per uid wins) and `save` (save until unsave; saves are NOT
window-pruned — a pin is a pin until the reader clears it).
"""

from __future__ import annotations

import json
import os
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from daily_digest.util import LOG

SCHEMA_VERSION = 1
RATING_ACTIONS = ("like", "dislike", "unlike", "undislike")
SAVE_ACTIONS = ("save", "unsave")
ACTIONS = RATING_ACTIONS + SAVE_ACTIONS

SNAPSHOT_TRUNCATE = 1000  # keeps every line far below any OS write granularity
TITLE_CAP = 80
TOPIC_ADJUST_STEP = 0.25
TOPIC_ADJUST_CLAMP = 1.0

_APPEND_LOCK = threading.Lock()

# Windows constants for the atomic append
_FILE_APPEND_DATA = 0x0004
_FILE_SHARE_READ = 0x00000001
_FILE_SHARE_WRITE = 0x00000002
_OPEN_ALWAYS = 4
_FILE_ATTRIBUTE_NORMAL = 0x80


@dataclass(frozen=True)
class FeedbackSignal:
    ts: str
    date: str
    uid: str
    action: str
    snapshot: dict = field(default_factory=dict)


@dataclass(frozen=True)
class FeedbackAggregate:
    ratings: dict[str, str] = field(
        default_factory=dict
    )  # uid -> "like"|"dislike" (last wins)
    likes: list[dict] = field(
        default_factory=list
    )  # snapshots of effectively-liked items
    dislikes: list[dict] = field(default_factory=list)
    saved: dict[str, dict] = field(default_factory=dict)  # uid -> latest save snapshot


def _truncate_snapshot(snapshot: dict) -> dict:
    """Keep lines small: cap text fields; keep the structured fields intact."""
    clean = dict(snapshot)
    for key in ("summary", "llm_summary"):
        value = clean.get(key)
        if isinstance(value, str) and len(value) > SNAPSHOT_TRUNCATE:
            clean[key] = value[:SNAPSHOT_TRUNCATE]
    return clean


def _append_line(path: Path, data: bytes) -> None:
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        kernel32.CreateFileW.restype = wintypes.HANDLE
        kernel32.CreateFileW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        handle = kernel32.CreateFileW(
            str(path),
            _FILE_APPEND_DATA,
            _FILE_SHARE_READ | _FILE_SHARE_WRITE,
            None,
            _OPEN_ALWAYS,
            _FILE_ATTRIBUTE_NORMAL,
            None,
        )
        if handle == wintypes.HANDLE(-1).value or not handle:
            raise OSError(
                f"CreateFileW failed for {path} (err {kernel32.GetLastError()})"
            )
        try:
            written = wintypes.DWORD(0)
            ok = kernel32.WriteFile(
                handle, data, len(data), ctypes.byref(written), None
            )
            if not ok or written.value != len(data):
                raise OSError(f"WriteFile incomplete ({written.value}/{len(data)})")
        finally:
            kernel32.CloseHandle(handle)
    else:
        fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY)
        try:
            os.write(fd, data)
        finally:
            os.close(fd)


def append_feedback(
    path: Path, uid: str, action: str, digest_date: str, snapshot: dict
) -> None:
    """Append one feedback line. One line == one atomic append; concurrent popup
    processes are safe (probe-verified). Raises only on hard IO failure."""
    if action not in ACTIONS:
        raise ValueError(f"unknown feedback action: {action!r}")
    record = {
        "v": SCHEMA_VERSION,
        "ts": datetime.now().isoformat(timespec="seconds"),
        "date": digest_date,
        "uid": uid,
        "action": action,
        "snapshot": _truncate_snapshot(snapshot),
    }
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with _APPEND_LOCK:  # serialize appends within THIS process (pywebview threads)
        _append_line(Path(path), line.encode("utf-8"))


def read_feedback(path: Path) -> list[FeedbackSignal]:
    """Tolerant read: skip unparseable/partial lines (concurrent writers may be
    mid-append); never raises for content problems. Missing file -> []."""
    path = Path(path)
    if not path.exists():
        return []
    signals: list[FeedbackSignal] = []
    try:
        raw_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        LOG.warning("feedback log unreadable (%s): %s — treating as empty", path, exc)
        return []
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
            if not isinstance(record, dict):
                continue
            signals.append(
                FeedbackSignal(
                    ts=str(record.get("ts", "")),
                    date=str(record.get("date", "")),
                    uid=str(record.get("uid", "")),
                    action=str(record.get("action", "")),
                    snapshot=record.get("snapshot")
                    if isinstance(record.get("snapshot"), dict)
                    else {},
                )
            )
        except json.JSONDecodeError:
            continue  # torn/partial line from a concurrent writer — skip
    return signals


def _parse_ts(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def aggregate(
    signals: list[FeedbackSignal], today: str, window_days: int = 14
) -> FeedbackAggregate:
    """Two-channel aggregation. Ratings: the LAST action per uid wins and older
    opposite ratings are forgotten (like->dislike counts ONCE, as dislike).
    Saves: last save snapshot per uid persists until an unsave (not windowed)."""
    cutoff = None
    try:
        cutoff = datetime.fromisoformat(today) - timedelta(days=window_days)
    except ValueError:
        cutoff = None

    last_rating: dict[str, tuple[datetime | None, str]] = {}
    saved: dict[str, dict] = {}
    for signal in signals:
        if signal.action in ("like", "dislike", "unlike", "undislike"):
            ts = _parse_ts(signal.ts)
            previous = last_rating.get(signal.uid)
            if previous is None or (
                ts is not None and (previous[0] is None or ts >= previous[0])
            ):
                if signal.action in ("like", "dislike"):
                    last_rating[signal.uid] = (ts, signal.action)
                else:  # unlike/undislike clears the rating
                    last_rating.pop(signal.uid, None)
        elif signal.action == "save":
            snapshot = dict(signal.snapshot or {})
            snapshot["uid"] = signal.uid  # the render/bridge need the uid inside
            saved[signal.uid] = snapshot
        elif signal.action == "unsave":
            saved.pop(signal.uid, None)

    likes: list[dict] = []
    dislikes: list[dict] = []
    # snapshot lookup: latest snapshot seen for each uid across all signals
    snapshots: dict[str, dict] = {}
    for signal in signals:
        if signal.snapshot:
            snapshots[signal.uid] = signal.snapshot
    for uid, (ts, rating) in last_rating.items():
        if cutoff is not None and ts is not None and ts < cutoff:
            continue  # rating older than the window — ignored
        snapshot = snapshots.get(uid) or {}
        entry = dict(snapshot)
        entry.setdefault("uid", uid)
        (likes if rating == "like" else dislikes).append(entry)
    return FeedbackAggregate(
        ratings={uid: value for uid, (_, value) in last_rating.items()},
        likes=likes,
        dislikes=dislikes,
        saved=saved,
    )


def _cap_title(title: str) -> str:
    title = " ".join(str(title).split())
    return title[:TITLE_CAP] + ("…" if len(title) > TITLE_CAP else "")


def reader_context_block(
    aggregate: FeedbackAggregate, profile_text: str = "", max_titles: int = 10
) -> str:
    """The shared bounded reader_context block: recent liked/disliked/pinned
    titles + the profile. Concatenation only (titles may contain braces).
    Returns '' when there is nothing to say."""
    lines: list[str] = []
    if aggregate.likes:
        titles = "; ".join(
            _cap_title(entry.get("title", "")) for entry in aggregate.likes[:max_titles]
        )
        lines.append("Recently LIKED by the reader: " + titles)
    if aggregate.dislikes:
        titles = "; ".join(
            _cap_title(entry.get("title", ""))
            for entry in aggregate.dislikes[:max_titles]
        )
        lines.append("Recently DISLIKED by the reader: " + titles)
    if aggregate.saved:
        titles = "; ".join(
            _cap_title(entry.get("title", ""))
            for entry in list(aggregate.saved.values())[:max_titles]
        )
        lines.append("Pinned by the reader for later reading: " + titles)
    if profile_text:
        lines.append(
            "About the reader's current work, in their own words: " + profile_text
        )
    if not lines:
        return ""
    return (
        "Reader's recent signals (use them to judge relevance):\n- "
        + "\n- ".join(lines)
        + "\n"
    )


def topic_adjustments(
    aggregate: FeedbackAggregate, topics: list[str]
) -> dict[str, float]:
    """Per-topic soft nudge from likes/dislikes: +0.25 per like hit, -0.25 per
    dislike hit, clamped ±1.0 per topic. (The ITEM-level clamp lives in
    score_item: the summed adjustment per item is bounded at ±1.5.)"""
    counts: dict[str, float] = {}
    for entries, sign in (
        (aggregate.likes, TOPIC_ADJUST_STEP),
        (aggregate.dislikes, -TOPIC_ADJUST_STEP),
    ):
        for entry in entries:
            text = f"{entry.get('title', '')} {entry.get('summary', '')}".lower()
            for topic in topics:
                if topic.lower() in text:
                    counts[topic] = counts.get(topic, 0.0) + sign
    return {
        topic: max(-TOPIC_ADJUST_CLAMP, min(TOPIC_ADJUST_CLAMP, value))
        for topic, value in counts.items()
    }


def pinned_items(aggregate: FeedbackAggregate, cap: int = 5) -> list[dict]:
    """Save snapshots, newest-last-saved first, capped. Callers compute the
    overflow (len(saved) - cap) for the '+N older' note."""
    entries = list(aggregate.saved.values())
    return [dict(entry) for entry in entries[:cap]]
