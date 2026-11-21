"""Unique, write-ahead digest backups used before destructive rebuilds."""

from __future__ import annotations

import shutil
from pathlib import Path

from daily_digest.util import LOG


def next_backup_path(source: Path, output_dir: Path) -> Path:
    """Return the first free ``<stem>-morning[-N].html`` path."""
    first = output_dir / f"{source.stem}-morning.html"
    if not first.exists():
        return first
    for number in range(2, 1000):
        candidate = output_dir / f"{source.stem}-morning-{number}.html"
        if not candidate.exists():
            return candidate
    raise OSError(f"could not find a free morning-backup name for {source.name}")


def backup_digest(source: Path, output_dir: Path) -> Path | None:
    """Copy a digest to a unique morning backup.

    Returns None when the source does not exist (nothing to protect). Any
    failure while copying propagates so callers can abort before rebuilding.
    """
    if not source.exists():
        return None
    output_dir.mkdir(parents=True, exist_ok=True)
    target = next_backup_path(source, output_dir)
    shutil.copyfile(source, target)
    LOG.info("digest backed up to %s", target)
    return target
