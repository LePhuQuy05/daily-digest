"""Pipeline state machine: idempotency, degradation, notify semantics, seen-set, corruption."""

import json

import daily_digest.pipeline as pipeline
from daily_digest.pipeline import merge_items, run_day
from daily_digest.sources import SourceError
from helpers import FakeLlmClient, llm_ok_json, make_config, make_item


def _items():
    return [
        make_item(
            id="hn:1",
            title="HN story about LLM tooling",
            url="https://example.com/a",
            source="hn",
            points=200,
        ),
        make_item(
            id="arxiv:2611.11111",
            title="arXiv paper on RLHF",
            url="https://arxiv.org/abs/2611.11111",
            source="arxiv",
        ),
        make_item(
            id="arxiv:2611.11111",
            title="arXiv paper on RLHF",
            url="https://huggingface.co/papers/2611.11111",
            source="hf_papers",
            points=42,
            summary="HF summary with extra detail",
        ),
        make_item(
            id="arxiv:2611.22222",
            title="Interpretability study",
            url="https://arxiv.org/abs/2611.22222",
            source="arxiv",
        ),
        make_item(
            id="hn:2",
            title="v3.0 released: open source agent framework",
            url="https://example.com/b",
            source="hn",
            points=90,
        ),
    ]


def _patch_fetch(monkeypatch, items, errors):
    monkeypatch.setattr(pipeline, "fetch_all", lambda client, config: (items, errors))


class NotifyRecorder:
    def __init__(self):
        self.calls = []

    def __call__(self, counts, path, cfg):
        self.calls.append(path)


def test_merge_keeps_hf_signal():
    merged = merge_items(_items())
    assert len(merged) == 4  # arxiv/hf duplicate collapsed
    dup = next(i for i in merged if i.id == "arxiv:2611.11111")
    assert dup.source == "hf_papers"  # HF provenance survives
    assert dup.points == 42
    assert "HF summary" in dup.summary


def test_run_day_happy_path_llm(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    _patch_fetch(monkeypatch, _items(), [])
    recorder = NotifyRecorder()

    result = run_day(
        config,
        "2026-11-18",
        llm_client=FakeLlmClient(llm_ok_json(8)),
        notify_fn=recorder,
    )

    assert result.exit_code == 0
    assert result.mode == "llm"
    assert result.item_count == 4  # 4 unique items (of 8 picks, 4 valid indices)
    assert result.degraded is False
    assert result.digest_path is not None and result.digest_path.exists()
    assert len(recorder.calls) == 1

    state = json.loads(config.state_path.read_text(encoding="utf-8"))
    assert state["days"]["2026-11-18"]["notified"] is True
    assert len(state["seen"]) == 4
    html = result.digest_path.read_text(encoding="utf-8")
    assert "arXiv paper on RLHF" in html
    assert not (config.output_dir / "latest.html").exists()  # backfill guard


def test_run_day_idempotent_same_date(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    _patch_fetch(monkeypatch, _items(), [])
    recorder = NotifyRecorder()

    run_day(
        config,
        "2026-11-18",
        llm_client=FakeLlmClient(llm_ok_json(8)),
        notify_fn=recorder,
    )
    result2 = run_day(
        config,
        "2026-11-18",
        llm_client=FakeLlmClient(llm_ok_json(8)),
        notify_fn=recorder,
    )

    assert result2.mode == "skipped"
    assert result2.exit_code == 0
    assert len(recorder.calls) == 1  # no second toast


def test_run_day_force_renotifies(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    _patch_fetch(monkeypatch, _items(), [])
    recorder = NotifyRecorder()
    client = FakeLlmClient(llm_ok_json(8))

    run_day(config, "2026-11-18", llm_client=client, notify_fn=recorder)
    result2 = run_day(
        config, "2026-11-18", llm_client=client, notify_fn=recorder, force=True
    )

    assert result2.mode == "llm"
    assert len(recorder.calls) == 2  # forced rerun re-notifies


def test_run_day_partial_source_failure_degrades(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    items = [i for i in _items() if i.source != "arxiv"]  # only hn + hf items
    _patch_fetch(monkeypatch, items, [SourceError("arxiv", "boom")])
    recorder = NotifyRecorder()

    result = run_day(
        config,
        "2026-11-18",
        llm_client=FakeLlmClient(llm_ok_json(8)),
        notify_fn=recorder,
    )

    assert result.exit_code == 1
    assert result.degraded is True
    assert result.sources_failed == ["arxiv"]
    assert result.digest_path is not None and result.digest_path.exists()
    assert len(recorder.calls) == 1  # toast still goes out with partial digest


def test_run_day_all_sources_failed_is_fatal(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    from daily_digest.sources import enabled_sources

    all_sources = enabled_sources(
        config
    )  # derive from the registry, not a hardcoded list
    _patch_fetch(monkeypatch, [], [SourceError(n, "boom") for n in all_sources])
    recorder = NotifyRecorder()

    result = run_day(
        config,
        "2026-11-18",
        llm_client=FakeLlmClient(llm_ok_json()),
        notify_fn=recorder,
    )

    assert result.exit_code == 2
    assert result.digest_path is None
    assert recorder.calls == []


def test_run_day_zero_items_healthy_sources(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    _patch_fetch(monkeypatch, [], [])
    recorder = NotifyRecorder()

    result = run_day(
        config,
        "2026-11-18",
        llm_client=FakeLlmClient(llm_ok_json()),
        notify_fn=recorder,
    )

    assert result.exit_code == 1  # quiet day, not fatal
    assert result.digest_path is None
    assert recorder.calls == []


def test_run_day_notify_failure_then_retry(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    _patch_fetch(monkeypatch, _items(), [])
    flaky = {"fail": True}
    calls = []

    def flaky_notify(counts, path, cfg):
        if flaky["fail"]:
            raise RuntimeError("toast exploded")
        calls.append(path)

    result1 = run_day(
        config,
        "2026-11-18",
        llm_client=FakeLlmClient(llm_ok_json(8)),
        notify_fn=flaky_notify,
    )
    state = json.loads(config.state_path.read_text(encoding="utf-8"))
    assert result1.exit_code == 1
    assert state["days"]["2026-11-18"]["notified"] is False  # two-phase state

    flaky["fail"] = False
    result2 = run_day(
        config,
        "2026-11-18",
        llm_client=FakeLlmClient(llm_ok_json(8)),
        notify_fn=flaky_notify,
    )
    state = json.loads(config.state_path.read_text(encoding="utf-8"))
    assert result2.exit_code == 0
    assert state["days"]["2026-11-18"]["notified"] is True
    assert len(calls) == 1


def test_run_day_heuristic_without_llm(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    _patch_fetch(monkeypatch, _items(), [])
    recorder = NotifyRecorder()

    result = run_day(config, "2026-11-18", llm_client=None, notify_fn=recorder)

    assert result.mode == "heuristic"
    assert result.exit_code == 1  # degraded until an API key is configured
    assert result.digest_path is not None and result.digest_path.exists()
    assert len(recorder.calls) == 1
    html = result.digest_path.read_text(encoding="utf-8")
    assert "heuristic" in html


def test_run_day_seen_set_suppresses_repeats_across_days(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    day1 = _items()
    _patch_fetch(monkeypatch, day1, [])
    run_day(
        config,
        "2026-11-18",
        llm_client=FakeLlmClient(llm_ok_json(8)),
        notify_fn=NotifyRecorder(),
    )

    day2 = [
        make_item(
            id="arxiv:2611.11111",
            title="arXiv paper on RLHF",
            url="https://arxiv.org/abs/2611.11111",
            source="arxiv",
        ),  # repeat
        make_item(
            id="arxiv:2611.90010",
            title="Brand new distillation paper",
            url="https://arxiv.org/abs/2611.90010",
            source="arxiv",
        ),
        make_item(
            id="arxiv:2611.90011",
            title="New quantization method",
            url="https://arxiv.org/abs/2611.90011",
            source="arxiv",
        ),
        make_item(
            id="hn:77",
            title="Fresh HN story about agents",
            url="https://example.com/fresh",
            source="hn",
            points=80,
        ),
    ]
    _patch_fetch(monkeypatch, day2, [])
    result = run_day(
        config,
        "2026-11-19",
        llm_client=FakeLlmClient(llm_ok_json(8)),
        notify_fn=NotifyRecorder(),
    )

    assert result.exit_code == 0
    assert result.item_count == 3  # the repeat was dropped
    html = result.digest_path.read_text(encoding="utf-8")
    assert "Brand new distillation paper" in html
    assert "arXiv paper on RLHF" not in html


def test_run_day_survives_corrupt_state(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    config.state_path.parent.mkdir(parents=True, exist_ok=True)
    config.state_path.write_text("{broken json!!", encoding="utf-8")
    _patch_fetch(monkeypatch, _items(), [])

    result = run_day(
        config,
        "2026-11-18",
        llm_client=FakeLlmClient(llm_ok_json(8)),
        notify_fn=NotifyRecorder(),
    )

    assert result.exit_code == 0
    json.loads(
        config.state_path.read_text(encoding="utf-8")
    )  # valid state after the run
    assert config.state_path.with_name(
        "state.json.corrupt"
    ).exists()  # corruption preserved for inspection


def test_run_day_no_notify_flag(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    _patch_fetch(monkeypatch, _items(), [])
    recorder = NotifyRecorder()

    result = run_day(
        config,
        "2026-11-18",
        llm_client=FakeLlmClient(llm_ok_json(8)),
        notify_enabled=False,
        notify_fn=recorder,
    )

    assert result.digest_path is not None and result.digest_path.exists()
    assert recorder.calls == []
    state = json.loads(config.state_path.read_text(encoding="utf-8"))
    assert (
        state["days"]["2026-11-18"]["notified"] is False
    )  # --no-notify must not block the real 09:00 toast


def test_run_day_opens_desktop_popup_window(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    _patch_fetch(monkeypatch, _items(), [])
    spawned: list = []

    def fake_spawn(path):
        spawned.append(path)
        return True

    monkeypatch.setattr(pipeline, "spawn_popup_detached", fake_spawn)
    run_day(
        config,
        "2026-11-18",
        llm_client=FakeLlmClient(llm_ok_json(8)),
        notify_fn=NotifyRecorder(),
    )
    assert len(spawned) == 1  # the desktop popup opened automatically
    assert spawned[0].exists()


def test_run_day_popup_even_when_toast_fails(tmp_path, monkeypatch):
    """The popup window is the delivery safety net: it must open even if the toast fails."""
    config = make_config(tmp_path)
    _patch_fetch(monkeypatch, _items(), [])
    spawned: list = []

    def fake_spawn(path):
        spawned.append(path)
        return True

    monkeypatch.setattr(pipeline, "spawn_popup_detached", fake_spawn)

    def broken_notify(counts, path, cfg):
        raise RuntimeError("toast exploded")

    result = run_day(
        config,
        "2026-11-18",
        llm_client=FakeLlmClient(llm_ok_json(8)),
        notify_fn=broken_notify,
    )
    assert result.exit_code == 1
    assert len(spawned) == 1


def test_run_day_no_notify_flag_skips_popup(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    _patch_fetch(monkeypatch, _items(), [])
    spawned: list = []

    def fake_spawn(path):
        spawned.append(path)
        return True

    monkeypatch.setattr(pipeline, "spawn_popup_detached", fake_spawn)
    run_day(
        config,
        "2026-11-18",
        llm_client=FakeLlmClient(llm_ok_json(8)),
        notify_enabled=False,
        notify_fn=NotifyRecorder(),
    )
    assert spawned == []  # --no-notify is a full test mode: no toast, no window
