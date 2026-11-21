"""Every catalog key must be consumed by Python or a Jinja/JS template."""

from __future__ import annotations

from pathlib import Path

from daily_digest.i18n import catalog_keys

ROOT = Path(__file__).resolve().parents[1]


def _source_blob() -> str:
    text: list[str] = []
    for path in (ROOT / "daily_digest").rglob("*.py"):
        if path.name == "i18n.py":
            continue  # the catalog itself is not usage
        text.append(path.read_text(encoding="utf-8"))
    for path in (ROOT / "templates").rglob("*.j2"):
        text.append(path.read_text(encoding="utf-8"))
    return "\n".join(text)


def test_no_unused_catalog_keys():
    blob = _source_blob()
    # These are intentionally consumed through helpers, not literal lookups.
    dynamic = {"overview_takeaway_marker"} | {
        f"section_{section}" for section in ("papers", "tech_news", "tools_releases")
    }
    unused = []
    for key in sorted(catalog_keys("vi")):
        if key in dynamic:
            continue
        if f'"{key}"' in blob or f"'{key}'" in blob or f"t.{key}" in blob:
            continue
        unused.append(key)
    assert unused == [], f"unused catalog keys: {unused}"
