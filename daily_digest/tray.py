"""System tray app: the digest is always one click (or Ctrl+Alt+D) away.

- Tray icon (indigo "D") sits in the Windows notification area, starts at login
  (Startup shortcut created by `daily-digest install-tray`).
- Left-click / double-click the icon  -> today's digest popup opens
- Right-click menu:
    Mở digest hôm nay (Ctrl+Alt+D)   -> popup with the latest digest
    Làm mới ngay (fetch + rank)      -> runs the full pipeline (--force): fresh
                                        fetch, LLM editor+writer, toast + popup
    Thoát                            -> closes the tray app
- Global hotkey Ctrl+Alt+D works from anywhere (registered via RegisterHotKey).

All actions spawn DETACHED pythonw processes, so windows outlive anything.
Spam-guarded: rapid repeat clicks within the guard window are ignored.
"""

from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path

from daily_digest.config import Config
from daily_digest.util import LOG, PROJECT_ROOT

ICON_PATH = PROJECT_ROOT / "assets" / "digest.ico"
ICON_SIZE = 256
OPEN_GUARD_SECONDS = 10.0
REFRESH_GUARD_SECONDS = 60.0

MOD_CONTROL = 0x0002
MOD_ALT = 0x0001
HOTKEY_VK_D = 0x44  # 'D'
WM_HOTKEY = 0x0312


def ensure_icon() -> Path:
    """Generate assets/digest.ico once (indigo rounded square + white D)."""
    if ICON_PATH.exists():
        return ICON_PATH
    from PIL import Image, ImageDraw, ImageFont

    size = ICON_SIZE
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=size // 5, fill=(99, 102, 241, 255)
    )
    font = None
    for candidate in (
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
    ):
        try:
            font = ImageFont.truetype(candidate, int(size * 0.62))
            break
        except OSError:
            continue
    if font is None:
        font = ImageFont.load_default()
    left, top, right, bottom = draw.textbbox((0, 0), "D", font=font)
    draw.text(
        ((size - (right - left)) / 2 - left, (size - (bottom - top)) / 2 - top),
        "D",
        font=font,
        fill=(255, 255, 255, 255),
    )
    ICON_PATH.parent.mkdir(parents=True, exist_ok=True)
    image.save(
        ICON_PATH,
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    LOG.info("tray icon generated at %s", ICON_PATH)
    return ICON_PATH


def _pythonw() -> Path:
    return PROJECT_ROOT / ".venv" / "Scripts" / "pythonw.exe"


def _spawn_detached(args: list[str]) -> bool:
    pythonw = _pythonw()
    if not pythonw.exists():
        LOG.warning("pythonw not found at %s — run 'uv sync'", pythonw)
        return False
    try:
        subprocess.Popen(  # noqa: S603
            [str(pythonw), *args],
            cwd=str(PROJECT_ROOT),
            creationflags=subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )
        return True
    except OSError as exc:
        LOG.error("failed to spawn %s: %s", args, exc)
        return False


class TrayActions:
    """Menu/hotkey actions with spam guards. Tested with a mocked clock/spawner."""

    def __init__(self, config: Config, clock=time.monotonic, spawner=_spawn_detached):
        self.config = config
        self.clock = clock
        self.spawn = spawner
        self._last_open: float = -1e9
        self._last_refresh: float = -1e9
        self._lock = threading.Lock()

    def open_digest(self) -> None:
        """Popup with the latest digest; if none exists yet, fetch one first."""
        now = self.clock()
        with self._lock:
            if now - self._last_open < OPEN_GUARD_SECONDS:
                LOG.info("tray: open request ignored (spam guard)")
                return
            self._last_open = now
        latest = self.config.output_dir / "latest.html"
        if latest.exists():
            LOG.info("tray: opening digest popup")
            self.spawn(["-m", "daily_digest", "open", "latest"])
        else:
            LOG.info("tray: no digest yet — running a fresh fetch instead")
            self.spawn(["-m", "daily_digest", "run", "--force"])

    def refresh_now(self) -> None:
        """Full pipeline rerun: fetch -> LLM editor+writer -> toast + popup."""
        now = self.clock()
        with self._lock:
            if now - self._last_refresh < REFRESH_GUARD_SECONDS:
                LOG.info("tray: refresh request ignored (spam guard)")
                return
            self._last_refresh = now
        LOG.info("tray: refreshing digest now (--force)")
        self.spawn(["-m", "daily_digest", "run", "--force"])


def _hotkey_thread(callback) -> threading.Thread:
    """Ctrl+Alt+D global hotkey via RegisterHotKey + a Windows message pump."""

    def loop() -> None:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        if not user32.RegisterHotKey(None, 1, MOD_CONTROL | MOD_ALT, HOTKEY_VK_D):
            LOG.info(
                "tray: Ctrl+Alt+D is already handled by the Desktop shortcut (Explorer) "
                "— the hotkey works via that path; the tray menu still works too"
            )
            return
        LOG.info("tray: hotkey Ctrl+Alt+D registered")
        msg = wintypes.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY:
                    try:
                        callback()
                    except Exception as exc:  # noqa: BLE001
                        LOG.error("tray hotkey action failed: %s", exc)
        finally:
            user32.UnregisterHotKey(None, 1)

    thread = threading.Thread(target=loop, name="daily-digest-hotkey", daemon=True)
    return thread


def run_tray(config: Config) -> None:
    """Create the tray icon and run its loop (blocks until 'Thoát')."""
    import pystray
    from PIL import Image

    actions = TrayActions(config)

    def menu_open(icon, item):
        actions.open_digest()

    def menu_refresh(icon, item):
        actions.refresh_now()

    def menu_quit(icon, item):
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem("Mở digest hôm nay (Ctrl+Alt+D)", menu_open, default=True),
        pystray.MenuItem("Làm mới ngay (fetch + LLM chọn lại)", menu_refresh),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Thoát", menu_quit),
    )
    icon_path = ensure_icon()
    with Image.open(icon_path) as img:
        icon_image = img.convert("RGBA")
    icon = pystray.Icon(
        "Daily AI Digest",
        icon=icon_image,
        title="Daily AI Digest — click để mở (Ctrl+Alt+D)",
        menu=menu,
    )
    _hotkey_thread(actions.open_digest).start()
    LOG.info("tray app running — click the tray icon or press Ctrl+Alt+D")
    icon.run()
    LOG.info("tray app stopped")
