"""Shared plumbing: paths, logging, atomic writes, JSON state, .env loader."""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG = logging.getLogger("daily_digest")


def setup_logging(
    log_dir: Path, level: str = "INFO", max_bytes: int = 1_048_576, backups: int = 5
) -> None:
    """Rotating file log + console echo when interactive. Safe under pythonw (stdout is None)."""
    log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger("daily_digest")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    file_handler = RotatingFileHandler(
        log_dir / "daily-digest.log",
        maxBytes=max_bytes,
        backupCount=backups,
        encoding="utf-8",
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
    )
    root.addHandler(file_handler)

    # pythonw.exe gives the process no console: stdout/stderr are None and any print() crashes.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
    else:
        _force_utf8(sys.stdout)
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
    else:
        _force_utf8(sys.stderr)
        if sys.stderr.isatty():
            console = logging.StreamHandler(sys.stderr)
            console.setFormatter(logging.Formatter("%(levelname)-7s %(message)s"))
            root.addHandler(console)


def _force_utf8(stream) -> None:
    """Windows consoles often default to legacy codepages (cp932/cp1252) that crash on
    non-ASCII output; reconfigure to UTF-8 so prints/logs never raise UnicodeEncodeError."""
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (
        AttributeError,
        OSError,
        ValueError,
    ):  # non-TextIOWrapper streams: leave as-is
        pass


def load_env_file(path: Path) -> dict[str, str]:
    """Minimal .env parser. Values do NOT override real environment variables."""
    parsed: dict[str, str] = {}
    if not path.exists():
        return parsed
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
        parsed[key] = value
    return parsed


def atomic_write_text(path: Path, text: str) -> None:
    """Write via a unique temp file + os.replace so readers never see a partial file.

    A fixed ``name.tmp`` is unsafe when a scheduled run and a popup action write
    concurrently; every write gets its own temp name in the target directory.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def load_json(path: Path) -> dict:
    """Load JSON state; a corrupt file is backed up and reset, never fatal."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError) as exc:
        backup = path.with_name(path.name + ".corrupt")
        try:
            os.replace(path, backup)
            LOG.warning(
                "state file %s was corrupt (%s); backed up to %s and reset",
                path,
                exc,
                backup,
            )
        except OSError:
            LOG.warning(
                "state file %s was corrupt (%s) and could not be backed up; reset",
                path,
                exc,
            )
        return {}


def save_json(path: Path, data: dict) -> None:
    atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False))


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")
