"""Windows shortcuts for one-click digest access.

Creates (PowerShell WScript.Shell, current user only — no admin):
- Desktop:  "Daily AI Digest.lnk"     -> opens the digest popup (hotkey Ctrl+Alt+D
             registered on the shortcut too, as an Explorer-level fallback)
- Startup:  "Daily AI Digest Tray.lnk" -> starts the tray app at login

Uninstall removes both .lnk files and stops a running tray process.
"""

from __future__ import annotations

import subprocess

from daily_digest.tray import ICON_PATH, ensure_icon
from daily_digest.util import LOG, PROJECT_ROOT

DESKTOP_LNK_NAME = "Daily AI Digest.lnk"
STARTUP_LNK_NAME = "Daily AI Digest Tray.lnk"


def _pythonw() -> str:
    pythonw = PROJECT_ROOT / ".venv" / "Scripts" / "pythonw.exe"
    if not pythonw.exists():
        raise FileNotFoundError(
            f"pythonw.exe not found at {pythonw} — run 'uv sync' first"
        )
    return str(pythonw)


def build_shortcuts_script() -> str:
    pythonw = _pythonw()
    ensure_icon()
    return f"""
$ws = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('Desktop')
$lnk = $ws.CreateShortcut("$desktop\\{DESKTOP_LNK_NAME}")
$lnk.TargetPath = '{pythonw}'
$lnk.Arguments = '-m daily_digest open latest'
$lnk.WorkingDirectory = '{PROJECT_ROOT}'
$lnk.IconLocation = '{ICON_PATH}'
$lnk.Hotkey = 'Ctrl+Alt+D'
$lnk.Save()
$startup = [Environment]::GetFolderPath('Startup')
$lnk2 = $ws.CreateShortcut("$startup\\{STARTUP_LNK_NAME}")
$lnk2.TargetPath = '{pythonw}'
$lnk2.Arguments = '-m daily_digest tray'
$lnk2.WorkingDirectory = '{PROJECT_ROOT}'
$lnk2.IconLocation = '{ICON_PATH}'
$lnk2.Save()
Write-Output "shortcuts created"
"""


def build_uninstall_script() -> str:
    """Remove both .lnk files and stop any running tray process (pythonw -m daily_digest tray)."""
    return (
        "$desktop = [Environment]::GetFolderPath('Desktop')\n"
        f'Remove-Item "$desktop\\{DESKTOP_LNK_NAME}" -ErrorAction SilentlyContinue\n'
        "$startup = [Environment]::GetFolderPath('Startup')\n"
        f'Remove-Item "$startup\\{STARTUP_LNK_NAME}" -ErrorAction SilentlyContinue\n'
        "Get-CimInstance Win32_Process -Filter \"Name = 'pythonw.exe'\" | "
        "Where-Object { $_.CommandLine -match 'daily_digest tray' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }\n"
        'Write-Output "shortcuts removed, tray stopped"'
    )


def _run_ps(script: str) -> tuple[bool, str]:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        timeout=120,
    )
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode == 0, output.strip()


def install_shortcuts() -> tuple[bool, str]:
    ok, output = _run_ps(build_shortcuts_script())
    if ok:
        LOG.info("shortcuts installed (Desktop + Startup tray)")
    else:
        LOG.error("shortcut install failed: %s", output)
    return ok, output


def uninstall_shortcuts() -> tuple[bool, str]:
    ok, output = _run_ps(build_uninstall_script())
    if ok:
        LOG.info("shortcuts removed; tray stopped")
    else:
        LOG.error("shortcut uninstall failed: %s", output)
    return ok, output
