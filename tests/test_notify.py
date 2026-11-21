from daily_digest.config import NotifyCfg
from daily_digest.i18n import t
from daily_digest.notify import file_uri, notify, toast_launch_uri


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


def test_notify_uses_digest_locale(tmp_path, monkeypatch):
    import daily_digest.notify as notify_mod

    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(
        notify_mod,
        "send_toast",
        lambda title, body, path, cfg: sent.append((title, body)),
    )
    digest = tmp_path / "digest.html"
    digest.write_text('<html lang="ja"><body></body></html>', encoding="utf-8")

    notify({"papers": 3, "tech_news": 2}, digest, NotifyCfg())

    assert sent == [("Daily AI Digest", t("ja", "toast_body").format(n=5))]
