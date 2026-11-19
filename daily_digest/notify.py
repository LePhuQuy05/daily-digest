"""Native Windows toast notification.

Clicking the toast opens the DIGEST POPUP WINDOW (default) or the browser (file mode) —
protocol activation is handled by the OS, so it still works after this process exits.
"""

from __future__ import annotations

from pathlib import Path

from daily_digest.config import NotifyCfg
from daily_digest.model import SECTIONS
from daily_digest.util import LOG

SECTION_SHORT = {"papers": "papers", "tech_news": "news", "tools_releases": "tools"}

SCHEME = "dailydigest"


def file_uri(path: Path) -> str:
    return Path(path).resolve().as_uri()


def toast_launch_uri(cfg: NotifyCfg, digest_path: Path | None) -> str | None:
    """URI the toast activates on click. Pure function (unit-tested).

    popup -> dailydigest://latest  (desktop popup window; scheme registered by install-task)
    file  -> file:///...digest.html (opens the default browser)
    none  -> no click action
    """
    if cfg.launch == "none":
        return None
    if cfg.launch == "file":
        if digest_path is None or not digest_path.exists():
            return None
        return file_uri(digest_path)
    if cfg.launch == "popup":
        return f"{SCHEME}://latest"
    LOG.warning(
        "unknown notify.launch %r — toast will have no click action", cfg.launch
    )
    return None


def send_toast(title: str, body: str, digest_path: Path | None, cfg: NotifyCfg) -> None:
    """Show one toast. Raises on failure; the pipeline treats that as degraded (exit 1)."""
    if not cfg.enabled:
        LOG.info("notifications disabled (notify.enabled=false)")
        return
    # Imported lazily so tests and non-Windows dev machines don't need winrt.
    from windows_toasts import InteractableWindowsToaster, Toast

    uri = toast_launch_uri(cfg, digest_path)
    toaster = InteractableWindowsToaster("Daily AI Digest")
    toast = Toast()
    toast.text_fields = [title, body]
    if uri:
        toast.launch_action = uri
        LOG.info("toast will open %s on click", uri)
    toaster.show_toast(toast)
    LOG.info("toast shown: %s", title)


def notify(counts: dict[str, int], digest_path: Path, cfg: NotifyCfg) -> None:
    parts = [
        f"{counts.get(section, 0)} {SECTION_SHORT[section]}"
        for section in SECTIONS
        if counts.get(section)
    ]
    body = (
        " · ".join(parts) + " — click to open"
        if parts
        else "your digest is ready — click to open"
    )
    send_toast("Daily AI Digest", body, digest_path, cfg)
