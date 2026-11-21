import pytest

from daily_digest.ranking import select
from daily_digest.ranking.heuristic import (
    balanced_pool,
    default_section,
    rank_heuristic,
)
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


def test_balanced_pool_reserves_news_and_tool_slots(tmp_path):
    config = make_config(tmp_path)
    papers = [
        make_item(
            id=f"arxiv:{i}",
            title=f"LLM paper {i}",
            url=f"https://arxiv.org/abs/{i}",
            source="arxiv",
        )
        for i in range(60)
    ]
    news = [
        make_item(
            id=f"hn:{i}",
            title=f"AI product news {i}",
            url=f"https://example.com/news/{i}",
            source="hn",
            points=50 + i,
        )
        for i in range(10)
    ]
    tools = [
        make_item(
            id=f"gh:{i}",
            title=f"v{i}.0.0",
            url=f"https://github.com/example/repo/releases/tag/v{i}.0.0",
            source="gh_vllm",
            section_hint="tools_releases",
        )
        for i in range(5)
    ]
    pool = balanced_pool(papers + news + tools, config, cap=20)
    sections = [default_section(item) for item in pool]

    assert len(pool) == 20
    assert sections.count("tech_news") == 8
    assert sections.count("tools_releases") == 5
    assert sections.count("papers") == 7


def test_balanced_pool_drops_off_topic_hn_links(tmp_path):
    config = make_config(tmp_path)
    off_topic = [
        make_item(
            id=f"hn:off{i}",
            title=f"City council budget item {i}",
            url=f"https://example.com/off/{i}",
            source="hn",
            points=900,
        )
        for i in range(20)
    ]
    on_topic = [
        make_item(
            id=f"hn:ai{i}",
            title=f"New LLM agent release {i}",
            url=f"https://example.com/ai/{i}",
            source="hn",
            points=20,
        )
        for i in range(3)
    ]
    papers = [
        make_item(
            id=f"arxiv:{i}",
            title=f"LLM paper {i}",
            url=f"https://arxiv.org/abs/{i}",
            source="arxiv",
        )
        for i in range(40)
    ]
    pool = balanced_pool(off_topic + on_topic + papers, config, cap=20)
    titles = [item.title for item in pool]

    assert not any("City council" in title for title in titles)
    assert any("LLM agent release" in title for title in titles)


def test_default_section_honors_source_hint():
    tool = make_item(
        id="feed:abc",
        title="v0.34.0",
        url="https://github.com/vllm-project/vllm/releases/tag/v0.34.0",
        source="gh_vllm",
        section_hint="tools_releases",
    )
    assert default_section(tool) == "tools_releases"


def test_llm_accepts_tech_news_for_feed_sources(tmp_path):
    config = make_config(tmp_path)
    items = [
        make_item(
            id=f"feed:{i}",
            title=f"AI lab update {i}",
            url=f"https://example.com/update-{i}",
            source="openai_news",
            section_hint="tech_news",
        )
        for i in range(3)
    ]
    response = (
        '{"selected": ['
        '{"id": 0, "why": "w0", "section": "tech_news"},'
        '{"id": 1, "why": "w1", "section": "tech_news"},'
        '{"id": 2, "why": "w2", "section": "tools_releases"}'
        "]}"
    )
    ranked = rank_with_llm(items, FakeChat(response), config)

    assert [r.section for r in ranked] == ["tech_news", "tech_news", "tools_releases"]


def test_llm_keeps_release_feed_items_in_tools(tmp_path):
    config = make_config(tmp_path)
    items = [
        make_item(
            id=f"feed:{i}",
            title=f"v{i}.0.0",
            url=f"https://github.com/example/repo/releases/tag/v{i}.0.0",
            source="gh_vllm",
            section_hint="tools_releases",
        )
        for i in range(3)
    ]
    response = (
        '{"selected": ['
        '{"id": 0, "why": "w0", "section": "tech_news"},'
        '{"id": 1, "why": "w1", "section": "tech_news"},'
        '{"id": 2, "why": "w2", "section": "tools_releases"}'
        "]}"
    )
    ranked = rank_with_llm(items, FakeChat(response), config)

    assert [r.section for r in ranked] == [
        "tools_releases",
        "tools_releases",
        "tools_releases",
    ]


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


def _many_items(count: int):
    return [
        make_item(
            id=f"arxiv:{i}",
            title=f"Paper {i}",
            url=f"https://arxiv.org/abs/{i}",
            source="arxiv",
            summary="a paper about language models",
        )
        for i in range(count)
    ]


def test_select_respects_target_30(tmp_path):
    config = make_config(tmp_path)
    config.llm.top_n = 12
    ranked, mode = select(
        _many_items(40), FakeLlmClient(llm_ok_json(30)), config, target=30
    )
    assert mode == "llm"
    assert len(ranked) == 30


def test_select_target_short_pool_does_not_pad(tmp_path):
    config = make_config(tmp_path)
    ranked, mode = select(
        _many_items(2), FakeLlmClient(llm_ok_json(2)), config, target=5
    )
    assert mode == "llm"
    assert len(ranked) == 2


def test_select_target_1_and_2_accept_small_selection(tmp_path):
    config = make_config(tmp_path)
    for target in (1, 2):
        ranked, mode = select(
            _many_items(4),
            FakeLlmClient(llm_ok_json(target)),
            config,
            target=target,
        )
        assert mode == "llm"
        assert len(ranked) == target


def test_editor_prompt_scales_to_30(tmp_path):
    config = make_config(tmp_path)
    chat = FakeChat(llm_ok_json(30))
    rank_with_llm(_many_items(40), chat, config, target=30)
    system = chat.calls[0][0]["content"]
    assert "select the 30" in system
    assert "7-8 papers" not in system
    assert "about 18 papers" in system


def test_editor_prompt_uses_balanced_mix_below_six(tmp_path):
    config = make_config(tmp_path)
    chat = FakeChat(llm_ok_json(3))
    rank_with_llm(_many_items(4), chat, config, target=3)
    system = chat.calls[0][0]["content"]
    assert "select the 3" in system
    assert "balanced papers / tech news / tools-releases" in system


def test_select_falls_back_to_heuristic_on_llm_error(tmp_path):
    config = make_config(tmp_path)
    ranked, mode = select(_items(config), FakeLlmClient(["garbage", "garbage"]), config)
    assert mode == "heuristic"
    assert len(ranked) == len(_items(config))


def test_select_without_client_is_heuristic(tmp_path):
    config = make_config(tmp_path)
    _, mode = select(_items(config), None, config)
    assert mode == "heuristic"
