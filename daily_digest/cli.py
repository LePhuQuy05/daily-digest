"""Command line interface: run | smoke | notify-test | install-task | uninstall-task | print-config | open."""

from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path

from daily_digest.config import Config, ConfigError, load_config, redacted_config_dict
from daily_digest.pipeline import run_day
from daily_digest.util import LOG, load_json, save_json, setup_logging


def get_llm_client(config: Config):
    """Build the LLM client when a key is present; otherwise None (heuristic mode)."""
    from daily_digest.ranking.llm import LlmClient

    api_key = os.environ.get(config.llm.api_key_env)
    if not api_key:
        LOG.info(
            "API key not set (env %s) — using heuristic ranking; add it to .env for LLM mode",
            config.llm.api_key_env,
        )
        return None
    state = load_json(config.state_path)
    session_id = state.get("llm_session")
    if not session_id:
        session_id = "ses_" + secrets.token_hex(16)
        state["llm_session"] = session_id
        save_json(config.state_path, state)
    return LlmClient(config, api_key, session_id)


def get_summarize_client(config: Config, editor_client):
    """The WRITER LLM: same key/session, its own (possibly cheaper) model.
    Returns the editor client itself when no separate model is configured."""
    from daily_digest.ranking.llm import LlmClient

    if editor_client is None or not config.llm.summarize:
        return None
    writer_model = (config.llm.summarize_model or "").strip()
    if not writer_model or writer_model == config.llm.model:
        return editor_client  # one model, two roles
    api_key = os.environ.get(config.llm.api_key_env)
    state = load_json(config.state_path)
    return LlmClient(config, api_key, state.get("llm_session", ""), model=writer_model)


def cmd_run(config: Config, args: argparse.Namespace) -> int:
    import httpx

    editor = get_llm_client(config)
    result = run_day(
        config,
        date=args.date,
        http=httpx.Client(timeout=30.0, follow_redirects=True),
        llm_client=editor,
        summary_client=get_summarize_client(config, editor),
        force=args.force,
        notify_enabled=not args.no_notify,
    )
    message = result.message or (
        f"{result.item_count} items ({result.mode}) -> {result.digest_path}"
        + (
            f" [degraded: {', '.join(result.sources_failed)}]"
            if result.sources_failed
            else ""
        )
    )
    (
        LOG.error
        if result.exit_code == 2
        else LOG.warning
        if result.exit_code
        else LOG.info
    )("run: %s", message)
    return result.exit_code


def cmd_smoke(config: Config, args: argparse.Namespace) -> int:
    import httpx

    from daily_digest.sources import fetch_all

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        items, errors = fetch_all(client, config)
    for error in errors:
        print(f"FAIL {error.source}: {error.reason}")
    by_source: dict[str, list] = {}
    for item in items:
        by_source.setdefault(item.source, []).append(item)
    for source, source_items in by_source.items():
        print(f"OK   {source}: {len(source_items)} items")
        for item in source_items[:3]:
            print(f"     - {item.title[:90]}")
    print(f"pool: {len(items)} items, {len(errors)} source(s) failed")
    if not items:
        print("smoke: no items fetched", file=sys.stderr)
        return 1
    return 0


def cmd_health(config: Config, args: argparse.Namespace) -> int:
    import httpx

    from daily_digest.sources.feeds import check_feeds

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        health = check_feeds(client, config.sources.feeds)
    for feed in health:
        status = "OK  " if feed.ok else "FAIL"
        line = f"{status} {feed.name}: {feed.item_count} items"
        if not feed.ok:
            line += f" — {feed.error}"
        print(line)
    ok = sum(1 for feed in health if feed.ok)
    print(f"feeds: {ok}/{len(health)} healthy")
    if not health:
        print("health: no feeds configured", file=sys.stderr)
        return 1
    return 0 if ok else 1


def cmd_notify_test(config: Config, args: argparse.Namespace) -> int:
    from daily_digest.notify import send_toast
    from daily_digest.popup import spawn_popup_detached

    latest = config.output_dir / "latest.html"
    if not latest.exists():
        latest.parent.mkdir(parents=True, exist_ok=True)
        latest.write_text(
            "<html><body style='font-family:sans-serif;padding:3em'>"
            "<h1>Daily Digest — popup test</h1>"
            "<p>If you can read this in a desktop window, the popup works. "
            "Clicking the toast opens the same window.</p></body></html>",
            encoding="utf-8",
        )
    send_toast(
        "Daily AI Digest", "This is a test toast — click me!", latest, config.notify
    )
    print("toast sent. Opening the desktop popup window now...")
    spawn_popup_detached(latest)
    print(f"  digest: {latest}")
    print("  (toast click -> same popup window; links inside open in your browser)")
    return 0


def cmd_print_config(config: Config, args: argparse.Namespace) -> int:
    import yaml

    yaml.safe_dump(
        redacted_config_dict(config), sys.stdout, sort_keys=False, allow_unicode=True
    )
    return 0


def resolve_digest_path(config: Config, target: str) -> Path:
    """Map 'latest' | YYYY-MM-DD | dailydigest://... | file path -> a digest Path."""
    if target.startswith("dailydigest://"):
        target = target[len("dailydigest://") :].strip("/\\") or "latest"
    if target in ("latest", ""):
        return config.output_dir / "latest.html"
    if re_match_date(target):
        return config.output_dir / f"digest-{target}.html"
    return Path(target)


def cmd_open(config: Config, args: argparse.Namespace) -> int:
    path = resolve_digest_path(config, args.target or "latest")
    if not path.exists():
        LOG.error("nothing to open at %s", path)
        return 1
    if args.web:
        os.startfile(str(path))  # noqa: S606
        return 0
    from daily_digest.popup import show_popup
    from daily_digest.popup_bridge import DigestBridge, extract_digest_data

    # The bridge is built from the digest's OWN embedded data blob — old digests
    # (no blob) get a read-only popup; feedback/ask stay hidden in the page.
    try:
        digest_data = extract_digest_data(path.read_text(encoding="utf-8"))
    except OSError as exc:
        LOG.warning("could not read digest data (%s); opening read-only", exc)
        digest_data = {}
    bridge = None
    if digest_data:
        try:
            bridge = DigestBridge(config, digest_data)
        except Exception as exc:  # noqa: BLE001 — read-only popup beats no popup
            LOG.warning(
                "bridge unavailable (%s: %s); opening read-only",
                type(exc).__name__,
                exc,
            )
            bridge = None

    try:
        show_popup(path, bridge=bridge)  # native desktop window; blocks until closed
        return 0
    except Exception as exc:  # noqa: BLE001 — never lose the digest over a window problem
        LOG.warning(
            "popup window failed (%s: %s); opening in browser instead",
            type(exc).__name__,
            exc,
        )
        os.startfile(str(path))  # noqa: S606
        return 0


def re_match_date(value: str) -> bool:
    import re

    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value))


def cmd_install_task(config: Config, args: argparse.Namespace) -> int:
    from daily_digest.taskinstall import install_task

    ok, output = install_task(config)
    print(output or ("installed: task will run daily at " + config.schedule.time))
    return 0 if ok else 1


def cmd_feedback(config: Config, args: argparse.Namespace) -> int:
    """Read-only feedback stats: action counts, effective ratings, saved list."""
    from daily_digest.feedback import aggregate, read_feedback, topic_adjustments
    from daily_digest.util import today_str

    signals = read_feedback(config.feedback_path)
    if not signals:
        print(f"no feedback yet ({config.feedback_path})")
        return 0
    agg = aggregate(signals, today_str(), config.feedback.window_days)
    counts: dict[str, int] = {}
    for signal in signals:
        counts[signal.action] = counts.get(signal.action, 0) + 1
    print(f"total signals: {len(signals)} ({config.feedback_path})")
    for action, count in sorted(counts.items()):
        print(f"  {action:10s} {count}")
    print(
        f"effective ratings (last {config.feedback.window_days}d): "
        f"{len(agg.likes)} liked / {len(agg.dislikes)} disliked"
    )
    if agg.saved:
        print(f"pinned ({len(agg.saved)}, showing {config.feedback.saved_cap}):")
        for entry in list(agg.saved.values())[: config.feedback.saved_cap]:
            print(f"  - {entry.get('title', '?')[:80]}")
    adjustments = topic_adjustments(agg, config.interests.topics)
    if adjustments:
        print("topic nudges (clamped ±1.0):")
        for topic, value in sorted(adjustments.items(), key=lambda kv: -abs(kv[1])):
            print(f"  {topic:20s} {value:+.2f}")
    return 0


def cmd_uninstall_task(config: Config, args: argparse.Namespace) -> int:
    from daily_digest.taskinstall import uninstall_task

    ok, output = uninstall_task()
    print(output or "scheduled task removed")
    return 0 if ok else 1


def cmd_tray(config: Config, args: argparse.Namespace) -> int:
    """Run the system tray app (blocks; normally started via the Startup shortcut)."""
    from daily_digest.tray import run_tray

    run_tray(config)
    return 0


def cmd_install_tray(config: Config, args: argparse.Namespace) -> int:
    """Desktop shortcut (double-click / Ctrl+Alt+D) + tray auto-start at login,
    then launch the tray right now so it appears without re-logging in."""
    from daily_digest.shortcuts import install_shortcuts
    from daily_digest.tray import TrayActions

    ok, output = install_shortcuts()
    print(output or "shortcuts created")
    if not ok:
        return 1
    if TrayActions(config).spawn(["-m", "daily_digest", "tray"]):
        print("tray is running: look for the indigo D icon near the clock.")
        print("  left-click -> digest popup | Ctrl+Alt+D anywhere -> digest popup")
        print("  right-click -> menu (làm mới ngay / thoát)")
    else:
        print(
            "shortcuts created, but the tray failed to start — it will start at next login",
            file=sys.stderr,
        )
    return 0


def cmd_uninstall_tray(config: Config, args: argparse.Namespace) -> int:
    from daily_digest.shortcuts import uninstall_shortcuts

    ok, output = uninstall_shortcuts()
    print(output or "shortcuts removed, tray stopped")
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="daily-digest", description="Daily AI & tech digest popup"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="path to config.yaml (default: project config.yaml)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser(
        "run", help="fetch, rank, write digest, notify (the daily job)"
    )
    run.add_argument(
        "--force", action="store_true", help="redo today even if already delivered"
    )
    run.add_argument(
        "--no-notify", action="store_true", help="skip the toast (testing)"
    )
    run.add_argument(
        "--date", default=None, help="backfill a specific date (YYYY-MM-DD)"
    )

    sub.add_parser("smoke", help="fetch all sources live and print counts")
    sub.add_parser("health", help="per-feed status for the curated feed source")
    sub.add_parser("notify-test", help="show a test toast that opens the digest")
    sub.add_parser("print-config", help="print effective config (secrets redacted)")
    sub.add_parser("install-task", help="register the daily Task Scheduler job")
    sub.add_parser("uninstall-task", help="remove the daily Task Scheduler job")
    sub.add_parser(
        "feedback", help="read-only feedback stats (likes/dislikes/pins/nudges)"
    )
    sub.add_parser(
        "tray", help="run the system tray app (one-click digest + Ctrl+Alt+D)"
    )
    sub.add_parser(
        "install-tray", help="create Desktop/Startup shortcuts and start the tray now"
    )
    sub.add_parser("uninstall-tray", help="remove shortcuts and stop the tray app")

    open_p = sub.add_parser(
        "open", help="open a digest (latest | YYYY-MM-DD | dailydigest://... | path)"
    )
    open_p.add_argument("target", nargs="?", default="latest")
    open_p.add_argument(
        "--web",
        action="store_true",
        help="open in the browser instead of the desktop popup window",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        setup_logging(
            config.log_dir, config.log.level, config.log.max_bytes, config.log.backups
        )
        handlers = {
            "run": cmd_run,
            "smoke": cmd_smoke,
            "health": cmd_health,
            "notify-test": cmd_notify_test,
            "print-config": cmd_print_config,
            "install-task": cmd_install_task,
            "uninstall-task": cmd_uninstall_task,
            "feedback": cmd_feedback,
            "tray": cmd_tray,
            "install-tray": cmd_install_tray,
            "uninstall-tray": cmd_uninstall_tray,
            "open": cmd_open,
        }
        return handlers[args.command](config, args)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except Exception:  # noqa: BLE001 — log full traceback for unattended runs, exit 2
        LOG.exception("unhandled error")
        print("unhandled error — see logs/daily-digest.log", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
