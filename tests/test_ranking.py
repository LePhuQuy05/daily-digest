import pytest

from daily_digest.ranking import select
from daily_digest.ranking.heuristic import rank_heuristic
from daily_digest.ranking.llm import LlmError, rank_with_llm
from helpers import FakeChat, FakeLlmClient, llm_ok_json, make_config, make_item


def _items(config):
    return [
        make_item(
            id="arxiv:1",
            title="LLM reasoning via RLHF",
            url="https://arxiv.org/abs/1",
            source="arxiv",
            summary="fine-tuning language models",
        ),
        make_item(
            id="hn:2",
            title="Local city council news",
            url="https://example.com/news",
            source="hn",
            points=500,
        ),
        make_item(
            id="arxiv:3",
            title="Interpretability of transformer circuits",
            url="https://arxiv.org/abs/3",
            source="arxiv",
        ),
        make_item(
            id="hn:4",
            title="Acme releases v2.0 of its open source database",
            url="https://example.com/v2",
            source="hn",
            points=90,
        ),
        make_item(
            id="arxiv:5",
            title="A physics paper about galaxies",
            url="https://arxiv.org/abs/5",
            source="arxiv",
        ),
        make_item(
            id="hn:6",
            title="AI agent framework benchmark results",
            url="https://example.com/agents",
            source="hn",
            points=120,
        ),
    ]


def test_heuristic_prioritizes_topic_hits_over_points(tmp_path):
    config = make_config(tmp_path)
    ranked = rank_heuristic(_items(config), config)

    assert ranked[0].item.title.startswith(
        ("LLM reasoning", "Interpretability", "AI agent")
    )
    positions = {r.item.title: index for index, r in enumerate(ranked)}
    # every on-topic item must outrank the 500-point off-topic story
    for title in (
        "LLM reasoning via RLHF",
        "Interpretability of transformer circuits",
        "AI agent framework benchmark results",
    ):
        assert positions[title] < positions["Local city council news"]
    assert (
        ranked[-1].item.title == "A physics paper about galaxies"
    )  # zero signal, zero points
    assert all(r.why for r in ranked), "heuristic mode must always produce a why line"


def test_heuristic_sections(tmp_path):
    config = make_config(tmp_path)
    ranked = {r.item.title: r.section for r in rank_heuristic(_items(config), config)}
    assert ranked["LLM reasoning via RLHF"] == "papers"
    assert ranked["Local city council news"] == "tech_news"
    assert ranked["Acme releases v2.0 of its open source database"] == "tools_releases"


def test_llm_ranking_valid_json_order_and_drop_rules(tmp_path):
    config = make_config(tmp_path)
    items = _items(config)
    response = (
        '{"selected": ['
        '{"id": 5, "why": "agent benchmarks matter", "section": "tech_news"},'
        '{"id": 0, "why": "core for the reader", "section": "papers"},'
        '{"id": 2, "why": "interp is core", "section": "papers"},'
        '{"id": 99, "why": "hallucinated index", "section": "papers"},'
        '{"id": 5, "why": "duplicate pick", "section": "tech_news"}'
        "]}"
    )
    ranked = rank_with_llm(items, FakeChat(response), config)
    # model order preserved; hallucinated and duplicate picks dropped
    assert [r.item.title for r in ranked] == [
        "AI agent framework benchmark results",
        "LLM reasoning via RLHF",
        "Interpretability of transformer circuits",
    ]
    assert ranked[0].why == "agent benchmarks matter"


def test_llm_accepts_fenced_json(tmp_path):
    config = make_config(tmp_path)
    response = "```json\n" + llm_ok_json(4) + "\n```"
    ranked = rank_with_llm(_items(config), FakeChat(response), config)
    assert len(ranked) == 4


def test_llm_repair_retry_recovers(tmp_path):
    config = make_config(tmp_path)
    chat = FakeChat(["oops, here are my picks instead:", llm_ok_json(4)])
    ranked = rank_with_llm(_items(config), chat, config)
    assert len(ranked) == 4
    assert len(chat.calls) == 2


def test_llm_invalid_json_twice_raises_llm_error(tmp_path):
    config = make_config(tmp_path)
    chat = FakeChat(["no json here at all", "still not json"])
    with pytest.raises(LlmError):
        rank_with_llm(_items(config), chat, config)
    assert len(chat.calls) == 2


def test_llm_too_few_valid_picks_raises(tmp_path):
    config = make_config(tmp_path)
    response = '{"selected": [{"id": 0, "why": "w", "section": "papers"}]}'
    with pytest.raises(LlmError):
        rank_with_llm(_items(config), FakeChat(response), config)


def test_llm_section_clamped_to_source_default(tmp_path):
    config = make_config(tmp_path)
    response = (
        '{"selected": ['
        '{"id": 0, "why": "w0", "section": "bogus_section"},'
        '{"id": 1, "why": "w1", "section": "papers"},'
        '{"id": 2, "why": "w2", "section": ""}'
        "]}"
    )
    ranked = rank_with_llm(_items(config), FakeChat(response), config)
    assert [r.section for r in ranked] == ["papers", "tech_news", "papers"]


def test_select_uses_llm_when_available(tmp_path):
    config = make_config(tmp_path)
    ranked, mode = select(_items(config), FakeLlmClient(llm_ok_json(4)), config)
    assert mode == "llm" and len(ranked) == 4


def test_select_falls_back_to_heuristic_on_llm_error(tmp_path):
    config = make_config(tmp_path)
    ranked, mode = select(_items(config), FakeLlmClient(["garbage", "garbage"]), config)
    assert mode == "heuristic"
    assert len(ranked) == len(_items(config))


def test_select_without_client_is_heuristic(tmp_path):
    config = make_config(tmp_path)
    _, mode = select(_items(config), None, config)
    assert mode == "heuristic"
