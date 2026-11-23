"""Version metadata stays in sync with the packaged project."""

from __future__ import annotations

import tomllib

from daily_digest import __version__
from daily_digest.util import PROJECT_ROOT


def test_version_matches_pyproject():
    data = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert __version__ == data["project"]["version"]
