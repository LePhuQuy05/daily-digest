"""F5 keyword rules: mute (hard drop, beats always), always (bonus + ★ALWAYS),
item-level clamp on feedback adjustments, pipeline mute-to-empty semantics."""

import json
import logging

import daily_digest.pipeline as pipeline
from daily_digest.config import Config, load_config
from daily_digest.model import Item
from daily_digest.pipeline import run_day
from daily_digest.ranking.heuristic import (
    ADJUSTMENT_ITEM_CLAMP,
    ALWAYS_BONUS,
    rank_heuristic,
    score_item,
)
from daily_digest.ranking.llm import _candidate_line
from daily_digest.rules import apply_mute, always_match, log_mute_summary, mute_match
from helpers import FakeLlmClient, llm_ok_json, make_config, make_item


def _with_rules(config, mute=(), always=()):
    config.interests.mute = list(mute)
    config.interests.always = list(always)
    return config


# ------------------------------------------------------------------ matching


def test_mute_match_case_insensitive_on_title_and_summary(tmp_path):
    config = _with_rules(make_config(tmp_path), mute=["NFT"])
    nft = make_item(
        id="hn:1",
        title="Huge NFT marketplace launch",
        url="https://x.io/a",
        source="hn",
    )
    crypto = make_item(
        id="hn:2",
        title="Study of whales",
        url="https://x.io/b",
        source="hn",
        summary="migration patterns",
    )
    assert mute_match(nft, config.interests.mute) == "NFT"
    assert mute_match(crypto, config.interests.mute) is None
    lower_hit = make_item(
        id="hn:3", title="all about nft royalties", url="https://x.io/c", source="hn"
    )
    assert mute_match(lower_hit, ["NFT"]) == "NFT"  # case-insensitive
    summary_hit = make_item(
        id="hn:4",
        title="Totally unrelated",
        url="https://x.io/d",
        source="hn",
        summary="mentions NFT sales",
    )
    assert mute_match(summary_hit, ["NFT"]) == "NFT"  # summary counts too


def test_apply_mute_returns_kept_and_dropped_pairs(tmp_path):
    config = _with_rules(make_config(tmp_path), mute=["quantum"])
    items = [
        make_item(
            id="hn:1", title="LLM agents released", url="https://x.io/1", source="hn"
        ),
        make_item(
            id="hn:2",
            title="Quantum computing breakthrough",
            url="https://x.io/2",
            source="hn",
        ),
        make_item(
            id="hn:3",
            title="RAG pipelines explained",
            url="https://x.io/3",
            source="hn",
        ),
    ]
    kept, dropped = apply_mute(items, config)
    assert [i.title for i in kept] == ["LLM agents released", "RAG pipelines explained"]
    assert [(item.title, keyword) for item, keyword in dropped] == [
        ("Quantum computing breakthrough", "quantum")
    ]


def test_mute_beats_always(tmp_path):
    config = _with_rules(make_config(tmp_path), mute=["crypto"], always=["crypto"])
    item = make_item(
        id="hn:1", title="crypto trading bots", url="https://x.io/1", source="hn"
    )
    kept, dropped = apply_mute([item], config)
    assert kept == [] and len(dropped) == 1  # muted even though it matches always


def test_mute_wrong_type_is_ignored_with_warning(tmp_path, caplog):
    import yaml

    path = tmp_path / "config.yaml"
    path.write_text("interests:\n  mute: crypto\n  always: 42\n", encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        config = load_config(path)
    assert config.interests.mute == [] and config.interests.always == []
    assert "must be a list" in caplog.text


# ------------------------------------------------------------------ always + heuristic


def test_always_bonus_lifts_score_and_pool_order(tmp_path):
    config = _with_rules(make_config(tmp_path), always=["vLLM"])
    plain = make_item(
        id="hn:1",
        title="Big LLM release with agents",
        url="https://x.io/1",
        source="hn",
        points=500,
    )
    must = make_item(
        id="hn:2",
        title="vLLM 3.0 benchmarks",
        url="https://x.io/2",
        source="hn",
        points=10,
    )
    assert (
        score_item(must, config)
        - score_item(_strip_always(must, config), _with_rules(make_config(tmp_path)))
        >= ALWAYS_BONUS
    )
    ranked = rank_heuristic([plain, must], config)
    assert (
        ranked[0].item.title == "vLLM 3.0 benchmarks"
    )  # tiny item beats the 500-pt one


def _strip_always(item, config):
    config.interests.always = []
    return item


def test_candidate_line_marks_always(tmp_path):
    config = _with_rules(make_config(tmp_path), always=["vLLM"])
    must = make_item(
        id="hn:1",
        title="vLLM 3.0 benchmarks",
        url="https://x.io/1",
        source="hn",
        points=42,
    )
    plain = make_item(
        id="hn:2", title="unrelated story", url="https://x.io/2", source="hn"
    )
    assert "★ALWAYS" in _candidate_line(0, must, config.interests.always)
    assert "★ALWAYS" not in _candidate_line(0, plain, config.interests.always)
    assert "★ALWAYS" not in _candidate_line(0, must)  # default: no always list


def test_adjustment_is_clamped_at_item_level(tmp_path):
    config = make_config(tmp_path)
    # the first configured topics, each adjusted +1.0 -> raw sum would exceed the clamp
    adjusted_topics = config.interests.topics[:6]
    assert len(adjusted_topics) >= 3, "test needs a topic-rich default config"
    hot_topics = {topic: 1.0 for topic in adjusted_topics}
    item = make_item(
        id="hn:1",
        title="LLM language model NLP reinforcement learning RLHF GRPO survey",
        url="https://x.io/1",
        source="hn",
    )
    hits = [
        topic
        for topic in adjusted_topics
        if topic.lower() in f"{item.title} {item.summary}".lower()
    ]
    assert len(hits) >= 3  # sanity: the item really hits multiple adjusted topics
    base = score_item(item, config)
    nudged = score_item(item, config, hot_topics)
    assert (
        abs((nudged - base) - ADJUSTMENT_ITEM_CLAMP) < 1e-9
    )  # capped at +1.5, not +len(hits)
    negative = {topic: -1.0 for topic in adjusted_topics}
    assert (
        abs((score_item(item, config, negative) - base) + ADJUSTMENT_ITEM_CLAMP) < 1e-9
    )


def test_adjustments_none_keeps_scoring_unchanged(tmp_path):
    config = make_config(tmp_path)
    item = make_item(
        id="hn:1", title="LLM paper", url="https://x.io/1", source="hn", points=100
    )
    assert score_item(item, config, None) == score_item(item, config)


# ------------------------------------------------------------------ pipeline


def _items():
    return [
        make_item(
            id="hn:1",
            title="HN story about LLM tooling",
            url="https://example.com/a",
            source="hn",
            points=200,
            summary="A big release in the agent tooling world.",
        ),
        make_item(
            id="arxiv:2611.11111",
            title="arXiv paper on RLHF",
            url="https://arxiv.org/abs/2611.11111",
            source="arxiv",
            summary="We study RLHF reward modeling at scale.",
        ),
        make_item(
            id="arxiv:2611.22222",
            title="NFT auction mechanism design",
            url="https://arxiv.org/abs/2611.22222",
            source="arxiv",
            summary="NFT market design.",
        ),
        make_item(
            id="hn:2",
            title="v3.0 released: open source agent framework",
            url="https://example.com/b",
            source="hn",
            points=90,
            summary="New major version.",
        ),
    ]


class _Notify:
    def __init__(self):
        self.calls = []

    def __call__(self, counts, path, cfg):
        self.calls.append(path)


def test_run_day_mutes_items_in_digest(tmp_path, monkeypatch):
    config = _with_rules(make_config(tmp_path), mute=["NFT"])
    monkeypatch.setattr(pipeline, "fetch_all", lambda client, cfg: (_items(), []))
    result = run_day(
        config,
        "2026-11-18",
        llm_client=FakeLlmClient(llm_ok_json(8)),
        notify_fn=_Notify(),
    )
    html = result.digest_path.read_text(encoding="utf-8")
    assert result.exit_code == 0
    assert "NFT auction mechanism design" not in html
    assert "arXiv paper on RLHF" in html


def test_run_day_overbroad_mute_warns(tmp_path, monkeypatch, caplog):
    config = _with_rules(make_config(tmp_path), mute=["e"])  # matches nearly everything
    monkeypatch.setattr(pipeline, "fetch_all", lambda client, cfg: (_items(), []))
    with caplog.at_level(logging.WARNING):
        result = run_day(
            config,
            "2026-11-18",
            llm_client=FakeLlmClient(llm_ok_json(8)),
            notify_fn=_Notify(),
        )
    assert result.exit_code == 0
    assert "too broad" in caplog.text


def test_run_day_mute_to_empty_renders_note_and_exits_zero(tmp_path, monkeypatch):
    config = _with_rules(
        make_config(tmp_path),
        mute=["arxiv", "agent", "release", "RLHF", "NFT", "story", "version"],
    )
    monkeypatch.setattr(pipeline, "fetch_all", lambda client, cfg: (_items(), []))
    result = run_day(
        config,
        "2026-11-18",
        llm_client=FakeLlmClient(llm_ok_json(8)),
        notify_fn=_Notify(),
    )
    assert result.exit_code == 0  # intentional empty digest is NOT degraded
    assert result.mode == "empty"
    assert result.item_count == 0
    html = result.digest_path.read_text(encoding="utf-8")
    assert "interests.mute đã lọc mất toàn bộ mục hôm nay" in html
    state = json.loads(config.state_path.read_text(encoding="utf-8"))
    assert state["days"]["2026-11-18"]["mode"] == "empty"


def test_run_day_without_mute_unchanged(tmp_path, monkeypatch):
    config = make_config(tmp_path)  # no rules configured
    monkeypatch.setattr(pipeline, "fetch_all", lambda client, cfg: (_items(), []))
    result = run_day(
        config,
        "2026-11-18",
        llm_client=FakeLlmClient(llm_ok_json(8)),
        notify_fn=_Notify(),
    )
    assert result.exit_code == 0
    html = result.digest_path.read_text(encoding="utf-8")
    assert "NFT auction mechanism design" in html  # untouched when no mute
