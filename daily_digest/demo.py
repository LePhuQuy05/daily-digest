"""Zero-key demo: render a bundled digest without network or LLM calls.

The demo exercises the real renderer and templates, so a reviewer can inspect the
UI immediately after `uv sync` without creating an API key or waiting for a run.
"""

from __future__ import annotations

import base64
import io
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from PIL import Image, ImageDraw, ImageOps

from daily_digest.config import Config
from daily_digest.i18n import normalize_locale, t
from daily_digest.media import ImageAsset
from daily_digest.model import Item, RankedItem, Section
from daily_digest.overview import ensure_coverage, parse_overview
from daily_digest.render import build_digest_data, render_digest
from daily_digest.util import atomic_write_text

DEMO_DATE = "2026-11-20"

DEMO_OVERVIEW = (
    "Hôm nay có ba hướng đáng chú ý. Về inference, [[0]] dùng một scorer nhẹ để "
    "quyết định evict KV nào, còn [[1]] chứng minh draft model hẹp vẫn giữ được "
    "tốc độ speculative decoding. [[2]] thì mang lại một benchmark agent nhỏ, "
    "chạy được trong CI.\n\n"
    "Về hạ tầng, [[3]] bổ sung tool calling native, [[4]] lý giải đường cong chi "
    "phí inference giảm, và [[5]] đưa vector search vào thẳng Postgres.\n\n"
    "Về công cụ, [[6]] chuẩn hóa eval tái lập được, [[7]] chạy GGUF trên thiết bị "
    "biên không cần Python.\n\n"
    "Điểm cần nhớ: nếu chỉ thử một thứ hôm nay, hãy đo lại chi phí decode sau khi "
    "bật KV eviction — đây là thay đổi ít rủi ro nhất trong danh sách."
)

DEMO_OVERVIEWS = {
    "vi": DEMO_OVERVIEW,
    "en": (
        "Three directions stand out today. On inference, [[0]] uses a lightweight "
        "scorer to decide which KV entries to evict, while [[1]] shows a narrow "
        "draft model can still keep speculative decoding fast. [[2]] contributes a "
        "small agent benchmark that runs in CI.\n\n"
        "On infrastructure, [[3]] adds native tool calling, [[4]] explains the "
        "falling inference-cost curve, and [[5]] brings vector search into Postgres.\n\n"
        "On tooling, [[6]] standardizes reproducible evals, and [[7]] runs GGUF on "
        "edge devices without Python.\n\n"
        "Key takeaway: if you try one thing today, re-measure decode cost after "
        "enabling KV eviction — it is the lowest-risk change on the list."
    ),
    "ja": (
        "本日は三つの方向が注目されています。推論では、[[0]] が軽量スコアラでKV"
        "キャッシュの破棄対象を決め、[[1]] は狭いドラフトモデルでも投機的デコー"
        "ディングの速度を保てることを示しています。[[2]] はCIで動く小さなエージェ"
        "ントbenchmarkを提供します。\n\n"
        "基盤では、[[3]] がネイティブのツール呼び出しを追加し、[[4]] は推論コスト"
        "低下の曲線を説明し、[[5]] はベクトル検索をPostgresに統合します。\n\n"
        "ツールでは、[[6]] が再現可能な評価を標準化し、[[7]] はPythonなしでGGUF"
        "をエッジ端末で動かします。\n\n"
        "要点: 今日一つだけ試すなら、KV evictionを有効にした後のdecodeコストを"
        "測り直すのが最もリスクの低い変更です。"
    ),
}

_DEMO_SPECS = (
    {
        "id": "demo:p1",
        "title": "KV Cache Eviction with Learned Token Importance",
        "url": "https://example.com/demo/kv-cache",
        "source": "arxiv",
        "section": "papers",
        "citations": 12,
        "why": "Directly reduces long-context inference cost.",
        "summary": (
            "A lightweight scorer ranks KV-cache entries by expected future "
            "attention, evicting 60% of the cache while keeping long-context "
            "accuracy within 0.4 points of full attention. It trains on 2k "
            "samples and adds less than 2% decode overhead."
        ),
    },
    {
        "id": "demo:p2",
        "title": "Narrow Draft Models for Speculative Decoding",
        "url": "https://example.com/demo/speculative",
        "source": "arxiv",
        "section": "papers",
        "citations": 8,
        "why": "A practical speedup that does not change the target model.",
        "summary": (
            "A 120M-parameter draft model, distilled from the target model's own "
            "rollouts, reaches a 2.1x decoding speedup on code and reasoning "
            "prompts. The authors show that acceptance-rate calibration matters "
            "more than draft-model size."
        ),
    },
    {
        "id": "demo:p3",
        "title": "AgentBench-Lite: A Small, Reproducible Tool-Use Benchmark",
        "url": "https://example.com/demo/agentbench",
        "source": "arxiv",
        "section": "papers",
        "citations": 5,
        "why": "Makes agent regressions visible without a huge harness.",
        "summary": (
            "A 300-task benchmark for tool selection and argument grounding, with "
            "deterministic graders and a single-command harness. It surfaces "
            "failure modes that aggregate agent benchmarks tend to hide."
        ),
    },
    {
        "id": "demo:t1",
        "title": "Open Model Release Adds Native Tool Calling",
        "url": "https://example.com/demo/tool-calling",
        "source": "hn",
        "section": "tech_news",
        "points": 420,
        "why": "A permissive model that is competitive on function calling.",
        "summary": (
            "The release adds structured tool calls, a 128k context window, and a "
            "permissive license. Early evaluations show competitive function-"
            "calling accuracy at a fraction of the inference cost."
        ),
    },
    {
        "id": "demo:t2",
        "title": "Why Inference Costs Keep Falling",
        "url": "https://example.com/demo/inference-costs",
        "source": "the_verge_ai",
        "section": "tech_news",
        "points": 310,
        "why": "Separates real algorithmic gains from hardware improvements.",
        "summary": (
            "A survey of the past year's cost curve: quantization, speculative "
            "decoding, and better batching compound to roughly 4x lower cost per "
            "million tokens. The analysis separates hardware gains from "
            "algorithmic gains."
        ),
    },
    {
        "id": "demo:t3",
        "title": "Postgres 19 Ships Built-in Vector Indexing",
        "url": "https://example.com/demo/postgres-vectors",
        "source": "ars_technica",
        "section": "tech_news",
        "points": 280,
        "why": "Removes a common extension dependency for small RAG apps.",
        "summary": (
            "The new index type brings HNSW-style approximate nearest-neighbor "
            "search into core Postgres. Early benchmarks show competitive recall "
            "at 10M vectors, with the operational simplicity of a single database."
        ),
    },
    {
        "id": "demo:d1",
        "title": "New CLI for Reproducible LLM Evals",
        "url": "https://example.com/demo/eval-cli",
        "source": "gh_vllm",
        "section": "tools_releases",
        "points": 150,
        "why": "Turns eval runs into diffable, CI-friendly artifacts.",
        "summary": (
            "A small CLI that pins prompts, model versions, and sampling "
            "parameters, then stores per-example outputs and scores. It is "
            "designed for CI and diffable eval reports rather than dashboards."
        ),
    },
    {
        "id": "demo:d2",
        "title": "Tiny Runtime Brings GGUF to the Edge",
        "url": "https://example.com/demo/gguf-edge",
        "source": "gh_ollama",
        "section": "tools_releases",
        "points": 120,
        "why": "Useful for offline assistants on low-power devices.",
        "summary": (
            "A 2 MB runtime runs quantized models on ARM CPUs with no Python "
            "dependency. The project targets offline assistants and includes a "
            "tokens-per-joule benchmark instead of token throughput alone."
        ),
    },
    {
        "id": "demo:d3",
        "title": "Open-Source Dashboard for Token Budgets",
        "url": "https://example.com/demo/token-budget",
        "source": "gh_openwebui",
        "section": "tools_releases",
        "points": 90,
        "why": "Makes model spend visible without sending logs to a SaaS.",
        "summary": (
            "A local-first dashboard that parses provider usage logs and shows "
            "spend by project, model, and day. It ships with a SQLite store, a "
            "single binary, and no telemetry."
        ),
    },
)


def _demo_image_asset() -> ImageAsset:
    """A deterministic abstract cover image, generated locally for the demo."""
    width, height = 1200, 630
    gradient = Image.linear_gradient("L").resize((width, height))
    image = ImageOps.colorize(gradient, black="#0B1B2B", white="#1D4ED8")
    draw = ImageDraw.Draw(image, "RGBA")
    draw.ellipse((600, -80, 1260, 580), fill=(159, 34, 78, 155))
    draw.ellipse((690, 80, 1110, 500), outline=(251, 250, 247, 180), width=3)
    for index in range(6):
        offset = index * 36
        draw.arc(
            (620, 40 + offset, 1180, 600 + offset),
            start=200,
            end=340,
            fill=(96, 165, 250, 80),
            width=2,
        )
    for x in range(80, 600, 80):
        draw.line((x, 0, x, height), fill=(251, 250, 247, 18), width=1)
    draw.rectangle((0, 0, 16, height), fill=(200, 16, 70, 220))
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=88)
    data_uri = "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()
    return ImageAsset(
        uid="demo:p1",
        data_uri=data_uri,
        alt="Abstract blue and crimson editorial illustration for the demo cover.",
        credit="Ảnh: demo fixture",
        source_url="https://example.com/demo/cover",
        kind="og",
        width=width,
        height=height,
    )


def _demo_ranked() -> list[RankedItem]:
    published = datetime(2026, 11, 20, 6, 0, tzinfo=timezone.utc)
    ranked: list[RankedItem] = []
    for spec in _DEMO_SPECS:
        item = Item(
            id=str(spec["id"]),
            title=str(spec["title"]),
            url=str(spec["url"]),
            source=str(spec["source"]),
            points=spec.get("points"),
            published=published,
            summary=str(spec["summary"]),
            citations=spec.get("citations"),
        )
        ranked.append(
            RankedItem(
                item=item,
                why=str(spec["why"]),
                section=cast(Section, spec["section"]),
                llm_summary=str(spec["summary"]),
            )
        )
    return ranked


def render_demo(
    config: Config, *, locale: str = "vi", open_browser: bool = True
) -> Path:
    """Render `output/demo.html` from bundled fixtures and optionally open it."""
    loc = normalize_locale(locale) or "vi"
    ranked = _demo_ranked()
    overview = DEMO_OVERVIEWS[loc]
    points = ensure_coverage(parse_overview(overview, ranked, loc), ranked, loc)
    html = render_digest(
        ranked,
        date=DEMO_DATE,
        mode="demo",
        degraded=False,
        sources_failed=[],
        model_name="demo fixtures",
        template=config.template_path,
        overview=overview,
        overview_label=t(loc, "overview_label"),
        overview_points=points,
        notice=t(loc, "demo_notice"),
        digest_data=build_digest_data(ranked, [], DEMO_DATE),
        pinned=[],
        images={"demo:p1": _demo_image_asset()},
        locale=loc,
    )
    path = config.output_dir / "demo.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, html)
    if open_browser:
        webbrowser.open(path.as_uri())
    return path
