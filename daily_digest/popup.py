"""Desktop popup window for the digest (native window via WebView2, NOT a browser tab).

Two entry points:
- show_popup(path):   blocking — opens the window in THIS process (used by `open`).
- spawn_popup_detached(path): fire-and-forget — launches a detached pythonw that shows
  the window; used by the daily run so the popup outlives the scheduled task process
  (the task has a 15-minute execution limit).
If the window cannot be created (e.g. WebView2 missing), callers fall back to the browser.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from daily_digest.util import LOG, PROJECT_ROOT

WINDOW_WIDTH = 980
WINDOW_HEIGHT = 1080


def show_popup(html_path: Path, title: str | None = None, bridge=None) -> None:
    """Open the digest in a native desktop window. Blocks until the window is closed.
    `bridge` (DigestBridge) becomes the pywebview js_api: feedback/ask actions
    from the page's JS call back into this process. None = read-only popup."""
    import webview

    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True  # paper links -> browser
    webview.create_window(
        title or f"Daily AI Digest — {html_path.stem}",
        html=html_path.read_text(encoding="utf-8"),
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        min_size=(720, 600),
        js_api=bridge,
    )
    webview.start()
    LOG.info("popup window closed: %s", html_path)


def spawn_popup_detached(html_path: Path) -> bool:
    """Launch a detached process that shows the popup window. Returns True if spawned."""
    pythonw = PROJECT_ROOT / ".venv" / "Scripts" / "pythonw.exe"
    if not pythonw.exists():
        LOG.warning("popup skipped: %s not found (run 'uv sync')", pythonw)
        return False
    try:
        subprocess.Popen(  # noqa: S603
            [str(pythonw), "-m", "daily_digest", "open", str(html_path)],
            cwd=str(PROJECT_ROOT),
            creationflags=subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )
    except OSError as exc:
        LOG.warning("popup spawn failed: %s", exc)
        return False
    LOG.info("popup window launched for %s", html_path)
    return True
