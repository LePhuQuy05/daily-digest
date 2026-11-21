"""Two-LLM digest: editor selects, writer summarizes. Contract, fallback, wiring."""

import dataclasses
import json
import logging

import httpx
import respx

import daily_digest.pipeline as pipeline
from daily_digest.config import Config
from daily_digest.model import Item, RankedItem
from daily_digest.pipeline import run_day
from daily_digest.ranking.llm import LlmClient, summarize_with_llm
from daily_digest.render import render_digest
from helpers import FakeChat, FakeLlmClient, llm_ok_json, make_config, make_item

GO_CHAT_URL = "https://opencode.ai/inference/go/openai/v1/chat/completions"


def _ranked(count: int = 4) -> list[RankedItem]:
    ranked = []
    for i in range(count):
        section = "papers" if i < 2 else "tech_news"
        source = "arxiv" if section == "papers" else "hn"
        item = Item(
            id=f"x:{i}",
            title=f"Paper {i} on LLM reasoning",
            url=f"https://arxiv.org/abs/2611.0000{i}",
            source=source,
            points=None if source == "arxiv" else 100 + i,
            summary=f"Original abstract {i}: we study reasoning in language models with method M{i}.",
        )
        ranked.append(RankedItem(item=item, why=f"why {i}", section=section))
    return ranked


def _summary_json(mapping: dict[int, str], overview: str = "") -> str:
    picks = ",".join(f'{{"id": {k}, "summary": "{v}"}}' for k, v in mapping.items())
    head = f'"overview": "{overview}", ' if overview else ""
    return f'{{{head}"items": [{picks}]}}'


# ------------------------------------------------------------------ summarizer contract


def test_summarize_sets_summaries(tmp_path):
    config = make_config(tmp_path)
    ranked = _ranked(4)
    response = _summary_json({0: "SUM-A", 1: "SUM-B", 2: "SUM-C", 3: "SUM-D"})
    out, overview = summarize_with_llm(ranked, FakeChat(response), config)
    assert [r.llm_summary for r in out] == ["SUM-A", "SUM-B", "SUM-C", "SUM-D"]
    assert all(r.item.summary for r in out)  # originals untouched
    assert out[0].why == "why 0"  # selection fields untouched
    assert overview == ""  # no overview in payload -> empty, pipeline falls back


def test_summarize_returns_day_overview(tmp_path):
    config = make_config(tmp_path)  # default overview_language: vi
    response = _summary_json(
        {0: "SUM-A"}, overview="Hôm nay nổi bật với các paper về reasoning và agents."
    )
    out, overview = summarize_with_llm(_ranked(1), FakeChat(response), config)
    assert out[0].llm_summary == "SUM-A"
    assert overview.startswith("Hôm nay")


def test_summarize_overview_truncated_and_cleaned(tmp_path):
    config = make_config(tmp_path)
    long_overview = "word " * 400  # ~2000 chars
    _, overview = summarize_with_llm(
        _ranked(1), FakeChat(_summary_json({0: "x"}, overview=long_overview)), config
    )
    assert 0 < len(overview) <= 1605
    assert "  " not in overview  # whitespace collapsed
    assert overview.endswith("…")  # word-boundary ellipsis, never mid-word


def test_ja_writer_sees_abstract_beyond_400_chars(tmp_path):
    config = make_config(tmp_path)
    ranked = _ranked(1)
    long_summary = ("A" * 800) + " MARKER-AT-800"
    ranked[0] = dataclasses.replace(
        ranked[0],
        item=dataclasses.replace(ranked[0].item, summary=long_summary),
    )
    chat = FakeChat(_summary_json({0: "これは日本語の要約です。"}))

    summarize_with_llm(ranked, chat, config, locale="ja")

    user_message = chat.calls[0][1]["content"]
    assert "MARKER-AT-800" in user_message


def test_overview_truncation_preserves_takeaway(tmp_path):
    config = make_config(tmp_path)
    long_head = "Long theme sentence. " * 120
    overview_text = long_head + "\n\nKey takeaway: keep this insight."
    _, overview = summarize_with_llm(
        _ranked(1),
        FakeChat(
            json.dumps(
                {
                    "overview": overview_text,
                    "items": [{"id": 0, "summary": "x"}],
                }
            )
        ),
        config,
        locale="en",
    )
    assert "Key takeaway: keep this insight." in overview
    assert len(overview) <= 1605


def test_overview_preserves_blank_lines_and_markers(tmp_path):
    config = make_config(tmp_path)
    text = "Hôm nay [[0]] dẫn đầu.\n\nĐiểm cần nhớ: [[1]] đáng đọc."
    response = json.dumps({"overview": text, "items": [{"id": 0, "summary": "x"}]})
    _, overview = summarize_with_llm(_ranked(2), FakeChat(response), config)
    assert "\n\n" in overview
    assert "[[0]]" in overview and "[[1]]" in overview


def test_overview_truncation_never_leaves_partial_marker(tmp_path):
    config = make_config(tmp_path)
    text = "x" * 1598 + " [[0]]"
    _, overview = summarize_with_llm(
        _ranked(1), FakeChat(_summary_json({0: "x"}, overview=text)), config
    )
    assert len(overview) <= 1605
    assert "[[0" not in overview  # incomplete marker removed at the cut


def test_overview_keeps_final_takeaway_under_budget(tmp_path):
    config = make_config(tmp_path)
    takeaway = "Điểm cần nhớ: ưu tiên đọc kỹ."
    overview_text = "Phân tích " * 150 + takeaway
    _, overview = summarize_with_llm(
        _ranked(1),
        FakeChat(_summary_json({0: "x"}, overview=overview_text)),
        config,
    )
    assert overview.endswith(takeaway)
    assert "…" not in overview


def test_summarize_non_dict_overview_is_ignored(tmp_path):
    config = make_config(tmp_path)
    response = (
        '{"overview": ["not", "a", "string"], "items": [{"id": 0, "summary": "ok"}]}'
    )
    out, overview = summarize_with_llm(_ranked(1), FakeChat(response), config)
    assert out[0].llm_summary == "ok" and overview == ""


def test_summarize_partial_coverage_keeps_fallback(tmp_path):
    config = make_config(tmp_path)
    ranked = _ranked(4)
    out, _ = summarize_with_llm(
        ranked, FakeChat(_summary_json({1: "only-this"})), config
    )
    assert out[1].llm_summary == "only-this"
    assert out[0].llm_summary == "" and out[3].llm_summary == ""


def test_summarize_drops_unknown_ids(tmp_path):
    config = make_config(tmp_path)
    ranked = _ranked(3)
    response = _summary_json({0: "ok", 99: "hallucinated", 1: "ok2"})
    out, _ = summarize_with_llm(ranked, FakeChat(response), config)
    assert out[0].llm_summary == "ok" and out[1].llm_summary == "ok2"
    assert all("hallucinated" not in r.llm_summary for r in out)


def test_summarize_accepts_fenced_json(tmp_path):
    config = make_config(tmp_path)
    response = (
        "```json\n"
        + _summary_json({0: "fenced summary"}, overview="TL;DR text")
        + "\n```"
    )
    out, overview = summarize_with_llm(_ranked(1), FakeChat(response), config)
    assert out[0].llm_summary == "fenced summary"
    assert overview == "TL;DR text"


def test_summarize_repair_retry_recovers(tmp_path):
    config = make_config(tmp_path)
    chat = FakeChat(["oops no json", _summary_json({0: "repaired"})])
    out, _ = summarize_with_llm(_ranked(1), chat, config)
    assert out[0].llm_summary == "repaired"
    assert len(chat.calls) == 2


def test_summarize_failure_returns_originals_unchanged(tmp_path):
    config = make_config(tmp_path)
    ranked = _ranked(3)
    chat = FakeChat(["not json", "still not json"])
    out, overview = summarize_with_llm(ranked, chat, config)
    assert out == ranked  # same objects, empty llm_summary -> raw abstracts shown
    assert overview == ""  # no overview either -> pipeline uses the mechanical one


def test_summarize_empty_selection_is_noop(tmp_path):
    config = make_config(tmp_path)
    assert summarize_with_llm([], FakeChat("whatever"), config) == ([], "")


def test_summarize_truncates_overlong_summaries(tmp_path):
    config = make_config(tmp_path)
    long_text = "word " * 400  # ~2000 chars
    out, _ = summarize_with_llm(
        _ranked(1), FakeChat(_summary_json({0: long_text})), config
    )
    assert len(out[0].llm_summary) <= 600


# ------------------------------------------------------------------ writer model override


@respx.mock
def test_llm_client_uses_model_override_in_request(tmp_path):
    config = make_config(tmp_path)
    route = respx.post(GO_CHAT_URL).respond(
        200, json={"choices": [{"message": {"content": "hi"}}]}
    )
    client = LlmClient(config, "test-key", "ses_test", model="glm-5.3-flash")
    assert client.chat([{"role": "user", "content": "hi"}]) == "hi"
    body = json.loads(route.calls.last.request.content)
    assert body["model"] == "glm-5.3-flash"
    assert body["max_tokens"] > 0


@respx.mock
def test_llm_client_defaults_to_editor_model(tmp_path):
    config = make_config(tmp_path)
    route = respx.post(GO_CHAT_URL).respond(
        200, json={"choices": [{"message": {"content": "hi"}}]}
    )
    client = LlmClient(config, "test-key", "ses_test")
    client.chat([{"role": "user", "content": "hi"}])
    body = json.loads(route.calls.last.request.content)
    assert body["model"] == "deepseek-v4.1-flash"  # the default editor model


@respx.mock
def test_llm_client_logs_finish_reason_and_usage(tmp_path, caplog):
    config = make_config(tmp_path)
    respx.post(GO_CHAT_URL).respond(
        200,
        json={
            "choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 7, "total_tokens": 10},
        },
    )
    client = LlmClient(config, "test-key", "ses_test")
    with caplog.at_level(logging.INFO, logger="daily_digest"):
        assert client.chat([{"role": "user", "content": "hi"}]) == "hi"
    assert "finish_reason=stop" in caplog.text
    assert "completion_tokens=7" in caplog.text


def test_writer_logs_response_prefix_on_parse_failure(tmp_path, caplog):
    config = make_config(tmp_path)
    with caplog.at_level(logging.DEBUG, logger="daily_digest"):
        summarize_with_llm(
            _ranked(1),
            FakeChat(["garbage", "garbage"]),
            config,
        )
    assert "writer response prefix" in caplog.text
    assert "garbage" in caplog.text


def test_get_summarize_client_reuses_editor_when_same_model(tmp_path):
    from daily_digest.cli import get_summarize_client

    config = make_config(tmp_path)
    editor = object()
    assert (
        get_summarize_client(config, editor) is editor
    )  # summarize_model empty -> same client
    config.llm.summarize_model = config.llm.model
    assert get_summarize_client(config, editor) is editor


def test_get_summarize_client_builds_writer_with_override(tmp_path, monkeypatch):
    from daily_digest.cli import get_summarize_client

    config = make_config(tmp_path)
    config.llm.summarize_model = "glm-5.3-flash"
    monkeypatch.setenv("OPENCODE_API_KEY", "test-key")
    state = {"llm_session": "ses_x"}
    config.state_path.write_text(json.dumps(state), encoding="utf-8")

    class FakeEditor:  # only needs to exist
        pass

    writer = get_summarize_client(config, FakeEditor())
    assert isinstance(writer, LlmClient)
    assert writer.model == "glm-5.3-flash"


def test_get_summarize_client_none_without_editor(tmp_path):
    from daily_digest.cli import get_summarize_client

    config = make_config(tmp_path)
    assert get_summarize_client(config, None) is None


# ------------------------------------------------------------------ pipeline integration


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
            id="arxiv:2611.11111",
            title="arXiv paper on RLHF",
            url="https://huggingface.co/papers/2611.11111",
            source="hf_papers",
            points=42,
            summary="We study RLHF reward modeling at scale with more detail.",
        ),
        make_item(
            id="arxiv:2611.22222",
            title="Interpretability study",
            url="https://arxiv.org/abs/2611.22222",
            source="arxiv",
            summary="Sparse autoencoders reveal circuits.",
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


class NotifyRecorder:
    def __init__(self):
        self.calls = []

    def __call__(self, counts, path, cfg):
        self.calls.append(path)


def test_run_day_enriches_digest_with_llm_summaries(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    monkeypatch.setattr(pipeline, "fetch_all", lambda client, cfg: (_items(), []))
    summaries = _summary_json(
        {0: "WRITER-SUM-0", 1: "WRITER-SUM-1", 2: "WRITER-SUM-2", 3: "WRITER-SUM-3"},
        overview="Hôm nay tập trung vào RLHF và interpretability, đáng chú ý nhất là paper reward modeling.",
    )

    result = run_day(
        config,
        "2026-11-18",
        llm_client=FakeLlmClient(llm_ok_json(8)),
        summary_client=FakeLlmClient(summaries),
        notify_fn=NotifyRecorder(),
    )
    assert result.exit_code == 0
    html = result.digest_path.read_text(encoding="utf-8")
    assert "WRITER-SUM-1" in html
    assert 'class="summary ai"' in html  # visually marked as LLM-written
    # the day-overview card is rendered at the top with the vi label
    assert "Tổng hợp hôm nay" in html
    assert "Hôm nay tập trung vào RLHF và interpretability" in html


def test_run_day_overview_falls_back_to_mechanical_when_writer_fails(
    tmp_path, monkeypatch
):
    config = make_config(tmp_path)  # overview_language: vi (default)
    monkeypatch.setattr(pipeline, "fetch_all", lambda client, cfg: (_items(), []))

    result = run_day(
        config,
        "2026-11-18",
        llm_client=FakeLlmClient(llm_ok_json(8)),
        summary_client=FakeLlmClient(["garbage", "garbage"]),
        notify_fn=NotifyRecorder(),
    )
    assert result.exit_code == 0
    html = result.digest_path.read_text(encoding="utf-8")
    assert "Tổng hợp hôm nay" in html  # the card still renders
    assert 'class="overview-point' in html  # structured fallback, not empty
    assert 'class="oref"' in html  # coverage refs are present
    assert "Nghiên cứu" in html or "Công nghệ" in html


def test_run_day_overview_without_summary_client_is_mechanical(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    config.llm.overview_language = "en"
    monkeypatch.setattr(pipeline, "fetch_all", lambda client, cfg: (_items(), []))

    result = run_day(
        config,
        "2026-11-18",
        llm_client=FakeLlmClient(llm_ok_json(8)),
        summary_client=None,
        notify_fn=NotifyRecorder(),
    )
    html = result.digest_path.read_text(encoding="utf-8")
    import html as html_mod

    decoded = html_mod.unescape(html)  # autoescape renders ' as &#39;
    assert "Today's overview" in decoded  # language-aware label
    assert 'class="overview-point' in decoded
    assert 'class="oref"' in decoded


def test_heuristic_overview_counts_and_themes(tmp_path):
    from daily_digest.ranking.heuristic import heuristic_overview, overview_label

    config = make_config(tmp_path)
    ranked = _ranked(4)  # 2 papers + 2 tech_news, titles mention LLM reasoning
    overview = heuristic_overview(ranked, config)
    assert overview.startswith("4 mục hôm nay")
    assert "2 bài báo" in overview and "2 tin công nghệ" in overview
    assert "LLM" in overview  # top theme from the items
    assert overview_label("vi") == "Tổng hợp hôm nay"

    assert overview_label("en") == "Today's overview"
    assert "items today" in heuristic_overview(ranked, config, "en")


def test_run_day_summary_failure_keeps_abstracts_and_delivery(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    monkeypatch.setattr(pipeline, "fetch_all", lambda client, cfg: (_items(), []))
    recorder = NotifyRecorder()

    result = run_day(
        config,
        "2026-11-18",
        llm_client=FakeLlmClient(llm_ok_json(8)),
        summary_client=FakeLlmClient(["garbage", "garbage"]),
        notify_fn=recorder,
    )
    assert result.exit_code == 0  # summary failure is not degraded
    html = result.digest_path.read_text(encoding="utf-8")
    assert "We study RLHF reward modeling" in html  # raw abstracts still shown
    assert len(recorder.calls) == 1  # toast delivered


def test_run_day_without_summary_client_keeps_abstracts(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    monkeypatch.setattr(pipeline, "fetch_all", lambda client, cfg: (_items(), []))

    result = run_day(
        config,
        "2026-11-18",
        llm_client=FakeLlmClient(llm_ok_json(8)),
        summary_client=None,
        notify_fn=NotifyRecorder(),
    )
    assert result.exit_code == 0
    html = result.digest_path.read_text(encoding="utf-8")
    assert "Sparse autoencoders reveal circuits." in html


def test_run_day_summary_disabled_via_config(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    config.llm.summarize = False
    monkeypatch.setattr(pipeline, "fetch_all", lambda client, cfg: (_items(), []))

    result = run_day(
        config,
        "2026-11-18",
        llm_client=FakeLlmClient(llm_ok_json(8)),
        summary_client=FakeLlmClient(_summary_json({0: "SHOULD-NOT-APPEAR"})),
        notify_fn=NotifyRecorder(),
    )
    assert result.exit_code == 0
    html = result.digest_path.read_text(encoding="utf-8")
    assert "SHOULD-NOT-APPEAR" not in html


# ------------------------------------------------------------------ rendering


def test_render_prefers_llm_summary_with_marker(tmp_path):
    config = make_config(tmp_path)
    item = make_item(
        id="arxiv:1",
        title="Paper about RAG",
        url="https://arxiv.org/abs/1",
        source="arxiv",
        summary="raw abstract text",
    )
    ranked = [
        RankedItem(
            item=item,
            why="core topic",
            section="papers",
            llm_summary="The paper introduces a retrieval method that cuts hallucinations.",
        )
    ]
    html = render_digest(
        ranked,
        date="2026-11-18",
        mode="llm",
        degraded=False,
        sources_failed=[],
        model_name="glm-5.3",
        template=config.template_path,
    )
    assert "The paper introduces a retrieval method" in html
    assert 'class="summary ai"' in html


def test_render_falls_back_to_raw_abstract(tmp_path):
    config = make_config(tmp_path)
    item = make_item(
        id="arxiv:1",
        title="Paper about RAG",
        url="https://arxiv.org/abs/1",
        source="arxiv",
        summary="raw abstract text",
    )
    ranked = [RankedItem(item=item, why="core topic", section="papers")]
    html = render_digest(
        ranked,
        date="2026-11-18",
        mode="llm",
        degraded=False,
        sources_failed=[],
        model_name="glm-5.3",
        template=config.template_path,
    )
    assert "raw abstract text" in html
    assert 'class="summary ai"' not in html  # no AI marker on raw abstracts


# ------------------------------------------------------------------ config knobs


def test_two_model_config_defaults():
    config = Config()
    assert config.llm.summarize is True
    assert config.llm.summarize_model == ""  # empty = same model as the editor
    assert config.llm.summary_max_words == 70


def test_two_model_config_yaml_and_env(tmp_path, monkeypatch):
    import yaml

    from daily_digest.config import load_config

    monkeypatch.setenv("DIGEST_LLM_SUMMARIZE_MODEL", "kimi-k3")
    config = load_config(tmp_path / "missing.yaml")
    assert config.llm.summarize_model == "kimi-k3"

    path = tmp_path / "config.yaml"
    path.write_text("llm:\n  summarize: false\n", encoding="utf-8")
    monkeypatch.delenv("DIGEST_LLM_SUMMARIZE_MODEL", raising=False)
    config = load_config(path)
    assert config.llm.summarize is False
