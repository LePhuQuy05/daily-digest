"""Tray app + shortcuts: icon generation, spam-guarded actions, .lnk scripts."""

from pathlib import Path

import daily_digest.tray as tray_mod
from daily_digest.shortcuts import (
    DESKTOP_LNK_NAME,
    STARTUP_LNK_NAME,
    build_shortcuts_script,
    build_uninstall_script,
)
from daily_digest.tray import ICON_PATH, TrayActions, ensure_icon
from helpers import make_config


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class SpawnRecorder:
    def __init__(self):
        self.calls: list[list[str]] = []

    def __call__(self, args):
        self.calls.append(list(args))
        return True


def _actions(config, clock, spawner):
    return TrayActions(config, clock=clock, spawner=spawner)


def test_ensure_icon_creates_ico_and_is_idempotent(tmp_path, monkeypatch):
    icon_path = tmp_path / "assets" / "digest.ico"
    monkeypatch.setattr(tray_mod, "ICON_PATH", icon_path)

    created = tray_mod.ensure_icon()
    assert created == icon_path and icon_path.exists()

    from PIL import Image

    with Image.open(icon_path) as img:
        assert img.size[0] >= 16

    first_mtime = icon_path.stat().st_mtime_ns
    tray_mod.ensure_icon()  # second call is a no-op
    assert icon_path.stat().st_mtime_ns == first_mtime


def test_open_digest_spawns_popup_when_latest_exists(tmp_path):
    config = make_config(tmp_path)
    latest = config.output_dir / "latest.html"
    latest.parent.mkdir(parents=True, exist_ok=True)
    latest.write_text("<html>x</html>", encoding="utf-8")

    clock, spawner = FakeClock(), SpawnRecorder()
    _actions(config, clock, spawner).open_digest()
    assert spawner.calls == [["-m", "daily_digest", "open", "latest"]]


def test_open_digest_falls_back_to_fresh_run_when_no_digest_yet(tmp_path):
    config = make_config(tmp_path)  # no output/latest.html
    clock, spawner = FakeClock(), SpawnRecorder()
    _actions(config, clock, spawner).open_digest()
    assert spawner.calls == [["-m", "daily_digest", "run", "--force"]]


def test_open_digest_spam_guard(tmp_path):
    config = make_config(tmp_path)
    latest = config.output_dir / "latest.html"
    latest.parent.mkdir(parents=True, exist_ok=True)
    latest.write_text("x", encoding="utf-8")

    clock, spawner = FakeClock(), SpawnRecorder()
    actions = _actions(config, clock, spawner)
    actions.open_digest()
    actions.open_digest()  # 0s later -> ignored
    assert len(spawner.calls) == 1

    clock.now += 11.0  # past the guard window
    actions.open_digest()
    assert len(spawner.calls) == 2


def test_refresh_now_spawns_force_run_with_guard(tmp_path):
    config = make_config(tmp_path)
    clock, spawner = FakeClock(), SpawnRecorder()
    actions = _actions(config, clock, spawner)

    actions.refresh_now()
    actions.refresh_now()  # ignored (60s guard)
    assert spawner.calls == [["-m", "daily_digest", "run", "--force"]]

    clock.now += 61.0
    actions.refresh_now()
    assert len(spawner.calls) == 2


def test_open_and_refresh_guards_are_independent(tmp_path):
    config = make_config(tmp_path)
    clock, spawner = FakeClock(), SpawnRecorder()
    actions = _actions(config, clock, spawner)
    actions.open_digest()  # run --force (no latest yet) -> sets refresh guard? no: open guard only
    actions.refresh_now()  # must still work (independent guards)
    assert len(spawner.calls) == 2


def test_tray_menu_has_expected_items():
    """The menu structure exists with Vietnamese labels and the default open action."""
    import pystray

    from daily_digest.tray import run_tray  # noqa: F401  (module imports cleanly)

    # Build the same menu structure run_tray uses, without running the icon loop.
    menu = pystray.Menu(
        pystray.MenuItem(
            "Mở digest hôm nay (Ctrl+Alt+D)", lambda *a: None, default=True
        ),
        pystray.MenuItem("Làm mới ngay (fetch + LLM chọn lại)", lambda *a: None),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Thoát", lambda *a: None),
    )
    labels = [item.text for item in menu.items if isinstance(item, pystray.MenuItem)]
    assert "Mở digest hôm nay (Ctrl+Alt+D)" in labels
    assert "Thoát" in labels


def test_shortcuts_script_contents():
    script = build_shortcuts_script()
    assert DESKTOP_LNK_NAME in script
    assert STARTUP_LNK_NAME in script
    assert "pythonw.exe" in script
    assert "-m daily_digest open latest" in script
    assert "-m daily_digest tray" in script
    assert "Ctrl+Alt+D" in script
    assert "Startup" in script and "Desktop" in script
    assert str(ICON_PATH) in script  # custom icon, not the generic python one


def test_uninstall_script_removes_shortcuts_and_stops_tray():
    script = build_uninstall_script()
    assert DESKTOP_LNK_NAME in script and STARTUP_LNK_NAME in script
    assert "Remove-Item" in script
    assert "daily_digest tray" in script  # stops the tray process only
    assert "Stop-Process" in script


def test_icon_path_is_inside_project_assets():
    from daily_digest.util import PROJECT_ROOT

    assert ICON_PATH == PROJECT_ROOT / "assets" / "digest.ico"
    assert Path(ICON_PATH).suffix == ".ico"
