"""Windows Task Scheduler registration for the 09:00 daily run.

Uses Register-ScheduledTask (PowerShell) because schtasks.exe cannot set
StartWhenAvailable (the "catch up if the PC was asleep" flag). The task runs
hidden via pythonw.exe, in the interactive user session — required for toasts.
"""

from __future__ import annotations

import subprocess

from daily_digest.config import Config
from daily_digest.util import LOG, PROJECT_ROOT

TASK_NAME = "Daily AI Digest"
SCHEME = "dailydigest"  # toast click -> dailydigest://latest -> desktop popup window


def _run_ps(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        timeout=120,
    )


def build_install_script(config: Config) -> str:
    pythonw = PROJECT_ROOT / ".venv" / "Scripts" / "pythonw.exe"
    if not pythonw.exists():
        raise FileNotFoundError(
            f"pythonw.exe not found at {pythonw} — run 'uv sync' first"
        )
    return (
        "$act = New-ScheduledTaskAction "
        f"-Execute '{pythonw}' -Argument '-m daily_digest run' -WorkingDirectory '{PROJECT_ROOT}'\n"
        f"$trg = New-ScheduledTaskTrigger -Daily -At '{config.schedule.time}'\n"
        "$set = New-ScheduledTaskSettingsSet -StartWhenAvailable "
        "-AllowStartIfOnBatteries -DontStopIfGoingOnBatteries "
        "-ExecutionTimeLimit (New-TimeSpan -Minutes 15) -MultipleInstances IgnoreNew\n"
        f"Register-ScheduledTask -TaskName '{TASK_NAME}' -Action $act -Trigger $trg -Settings $set -Force | Out-Null\n"
    )


def build_scheme_script() -> str:
    """Register the dailydigest:// URI scheme (HKCU, current user only) so toast clicks
    open the desktop popup window instead of the browser."""
    pythonw = PROJECT_ROOT / ".venv" / "Scripts" / "pythonw.exe"
    if not pythonw.exists():
        raise FileNotFoundError(
            f"pythonw.exe not found at {pythonw} — run 'uv sync' first"
        )
    handler = f'"{pythonw}" -m daily_digest open "%1"'
    root = rf"HKCU:\Software\Classes\{SCHEME}"
    return (
        f"New-Item -Path '{root}' -Force | Out-Null\n"
        f"Set-ItemProperty -Path '{root}' -Name '(Default)' -Value 'URL:Daily AI Digest'\n"
        f"Set-ItemProperty -Path '{root}' -Name 'URL Protocol' -Value ''\n"
        f"New-Item -Path '{root}\\shell\\open\\command' -Force | Out-Null\n"
        f"Set-ItemProperty -Path '{root}\\shell\\open\\command' -Name '(Default)' -Value '{handler}'\n"
    )


def install_task(config: Config) -> tuple[bool, str]:
    outputs: list[str] = []
    for label, script in (
        ("scheduled task", build_install_script(config)),
        ("URI scheme", build_scheme_script()),
    ):
        result = _run_ps(script)
        outputs.append((result.stdout or "") + (result.stderr or ""))
        if result.returncode != 0:
            LOG.error("%s install failed: %s", label, outputs[-1])
            return False, "\n".join(outputs).strip()
    LOG.info(
        "scheduled task '%s' installed for %s daily; %s:// scheme registered",
        TASK_NAME,
        config.schedule.time,
        SCHEME,
    )
    return True, "\n".join(outputs).strip()


def uninstall_task() -> tuple[bool, str]:
    root = rf"HKCU:\Software\Classes\{SCHEME}"
    script = (
        f"try {{ Unregister-ScheduledTask -TaskName '{TASK_NAME}' -Confirm:$false -ErrorAction Stop }} "
        "catch { if ($_.Exception.Message -notmatch 'No scheduled task') { throw } }\n"
        f"if (Test-Path '{root}') {{ Remove-Item -Path '{root}' -Recurse -Force }}\n"
    )
    result = _run_ps(script)
    output = (result.stdout or "") + (result.stderr or "")
    ok = result.returncode == 0
    if ok:
        LOG.info("scheduled task '%s' and %s:// scheme removed", TASK_NAME, SCHEME)
    else:
        LOG.error("task uninstall failed: %s", output)
    return ok, output.strip()
