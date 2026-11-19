from daily_digest.config import NotifyCfg
from daily_digest.notify import file_uri, toast_launch_uri


def test_launch_uri_popup_mode(tmp_path):
    digest = tmp_path / "digest-2026-11-18.html"
    digest.write_text("x", encoding="utf-8")
    assert toast_launch_uri(NotifyCfg(launch="popup"), digest) == "dailydigest://latest"


def test_launch_uri_file_mode(tmp_path):
    digest = tmp_path / "digest-2026-11-18.html"
    digest.write_text("x", encoding="utf-8")
    assert toast_launch_uri(NotifyCfg(launch="file"), digest) == file_uri(digest)
    assert toast_launch_uri(NotifyCfg(launch="file"), digest).startswith("file:///")


def test_launch_uri_file_mode_with_missing_digest(tmp_path):
    assert toast_launch_uri(NotifyCfg(launch="file"), tmp_path / "missing.html") is None


def test_launch_uri_none_mode(tmp_path):
    digest = tmp_path / "digest.html"
    digest.write_text("x", encoding="utf-8")
    assert toast_launch_uri(NotifyCfg(launch="none"), digest) is None


def test_launch_uri_unknown_mode_falls_back_to_no_action(tmp_path):
    digest = tmp_path / "digest.html"
    digest.write_text("x", encoding="utf-8")
    assert toast_launch_uri(NotifyCfg(launch="carrier-pigeon"), digest) is None
