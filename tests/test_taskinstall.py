from daily_digest import taskinstall
from daily_digest.config import Config
from daily_digest.taskinstall import (
    SCHEME,
    TASK_NAME,
    build_install_script,
    build_scheme_script,
)


def test_install_script_contains_required_flags():
    script = build_install_script(Config())
    assert "-WorkingDirectory" in script  # default action cwd is System32 without this
    assert "pythonw.exe" in script  # hidden run: no console window
    assert "StartWhenAvailable" in script  # catch-up when the PC was asleep
    assert "-AllowStartIfOnBatteries" in script  # laptops: digest must run on battery
    assert "-DontStopIfGoingOnBatteries" in script
    assert "MultipleInstances IgnoreNew" in script
    assert f"'{TASK_NAME}'" in script
    assert "'09:00'" in script
    assert "Register-ScheduledTask" in script


def test_scheme_script_registers_dailydigest_protocol():
    script = build_scheme_script()
    assert r"HKCU:\Software\Classes\dailydigest" in script
    assert "URL Protocol" in script  # marks the key as a URI scheme
    assert "pythonw.exe" in script
    assert '"%1"' in script  # the clicked URI is passed to the handler
    assert "-m daily_digest open" in script  # handler opens the desktop popup


def test_install_task_invokes_powershell_for_task_and_scheme(monkeypatch):
    scripts: list[str] = []

    class FakeCompleted:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run_ps(script):
        scripts.append(script)
        return FakeCompleted()

    monkeypatch.setattr(taskinstall, "_run_ps", fake_run_ps)
    ok, _ = taskinstall.install_task(Config())
    assert ok is True
    assert len(scripts) == 2
    assert "Register-ScheduledTask" in scripts[0]
    assert SCHEME in scripts[1]


def test_uninstall_task_removes_task_and_scheme(monkeypatch):
    scripts: list[str] = []

    class FakeCompleted:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run_ps(script):
        scripts.append(script)
        return FakeCompleted()

    monkeypatch.setattr(taskinstall, "_run_ps", fake_run_ps)
    ok, _ = taskinstall.uninstall_task()
    assert ok is True
    combined = "\n".join(scripts)
    assert "Unregister-ScheduledTask" in combined
    assert r"HKCU:\Software\Classes\dailydigest" in combined  # scheme removed too
