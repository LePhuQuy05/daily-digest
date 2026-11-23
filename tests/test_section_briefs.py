"""Section briefs, full More-band summaries, and structured notices."""

from __future__ import annotations

import json
import re
import time

import daily_digest.pipeline as pipeline
from daily_digest.edition import Edition, load_edition, save_edition
from daily_digest.i18n import t
from daily_digest.model import RankedItem
from daily_digest.overview import (
    complete_section_briefs,
    ensure_coverage,
    heuristic_section_briefs,
    parse_overview,
)
from daily_digest.pipeline import run_day
from daily_digest.ranking.llm import (
    summarize_with_llm,
    write_section_briefs,
    writer_deadline,
)
from daily_digest.render import build_digest_data, render_digest
from helpers import FakeLlmClient, llm_ok_json, make_config, make_item

DATE = "2026-11-23"


def _item(index: int, section: str) -> RankedItem:
    return RankedItem(
        item=make_item(
            id=f"arxiv:2611.{index:05d}",
            title=f"Story {index}",
            url=f"https://arxiv.org/abs/2611.{index:05d}",
            source="arxiv",
            summary=f"source summary {index}",
        ),
        why=f"why {index}",
        section=section,  # type: ignore[arg-type]
        llm_summary=f"llm summary {index}",
    )


def _mixed(count: int = 30) -> list[RankedItem]:
    sections = ("papers", "tech_news", "tools_releases")
    return [_item(i, sections[i % 3]) for i in range(count)]


def _render(tmp_path, ranked, **kwargs):
    config = make_config(tmp_path)
    return render_digest(
        ranked,
        date=DATE,
        mode="llm",
        degraded=False,
        sources_failed=[],
        model_name="test",
        template=config.template_path,
        locale=kwargs.pop("locale", "vi"),
        **kwargs,
    )


def test_all_thirty_items_show_a_summary_including_more(tmp_path):
    ranked = [_item(i, "papers") for i in range(30)]
    html = _render(
        tmp_path,
        ranked,
        section_briefs=heuristic_section_briefs(ranked, make_config(tmp_path)),
    )

    assert html.count('class="story story--more') == 21
    assert 'class="summary ai"' in html
    more_html = html[html.index('class="section-more') :]
    blocks = [block for block in more_html.split("<article") if "story--more" in block]
    assert len(blocks) == 21
    for block in blocks:
        uid = re.search(r'data-uid="([^"]+)"', block).group(1)
        index = int(uid.rsplit(".", 1)[1])
        assert f"llm summary {index}" in block
        assert 'class="summary ai"' in block
    css = (make_config(tmp_path).template_path.parent / "newsroom.css.j2").read_text(
        encoding="utf-8"
    )
    screen_rule = css[css.index(".section-more .story--more .summary") :]
    assert "-webkit-line-clamp: unset" in screen_rule[:300]
    print_rule = css[
        css.index(".section-more .story--more .summary { display: block") :
    ]
    assert "overflow: visible" in print_rule[:200]


def test_section_briefs_replace_global_rail_and_cover_every_uid(tmp_path):
    ranked = _mixed(30)
    briefs = heuristic_section_briefs(ranked, make_config(tmp_path))
    html = _render(tmp_path, ranked, section_briefs=briefs, overview="legacy overview")

    assert html.count('class="section-summary"') == 3
    assert 'class="section-summary-refs"' not in html
    assert 'id="briefing"' not in html
    assert "legacy overview" not in html
    assert "top-fold top-fold--cover" in html
    assert '<aside class="rail">' not in html
    assert html.count('class="source-line"') == 1
    assert html.count('class="oref"') == 30
    for item in ranked:
        assert f'data-story-ref="{item.item.id}"' in html
        assert f'href="#story-{item.item.id}"' in html
    data = build_digest_data(ranked, [], DATE)
    assert set(data) == {"date", "items", "pinned"}


def test_section_brief_validation_drops_wrong_section_and_extra_refs(tmp_path):
    config = make_config(tmp_path)
    ranked = _mixed(12)
    payload = {
        "sections": [
            {
                "section": "papers",
                "text": "Papers [[0]], [[3]], [[6]], [[9]]. " + "A" * 250,
                "refs": [0, 1, 3, 6, 9],
            },
            {
                "section": "tech_news",
                "text": "Tech [[1]], [[4]], [[7]], [[10]].",
                "refs": [1, 4, 7, 10],
            },
            {"section": "unknown", "text": "ignored", "refs": [0]},
        ]
    }
    chat = FakeLlmClient(json.dumps(payload))

    briefs = write_section_briefs(ranked, chat.chat, config, locale="en", deadline=None)

    assert len(briefs) == 2
    papers = next(brief for brief in briefs if brief.section == "papers")
    assert len(papers.text) <= 500
    assert [ref.uid for ref in papers.refs] == [
        ranked[0].item.id,
        ranked[3].item.id,
        ranked[6].item.id,
        ranked[9].item.id,
    ]
    assert papers.segments and papers.segments[1].ref is not None
    news = next(brief for brief in briefs if brief.section == "tech_news")
    assert [ref.uid for ref in news.refs] == [
        ranked[1].item.id,
        ranked[4].item.id,
        ranked[7].item.id,
        ranked[10].item.id,
    ]


def _mixed_selection(count: int) -> str:
    sections = ("papers", "tech_news", "tools_releases")
    picks = ",".join(
        f'{{"id": {i}, "why": "why {i}", "section": "{sections[i % 3]}"}}'
        for i in range(count)
    )
    return f'{{"selected": [{picks}]}}'


def test_pipeline_falls_back_to_mechanical_section_briefs(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    items = [
        make_item(
            id=f"arxiv:2611.{i:05d}",
            title=f"Fallback story {i}",
            url=f"https://arxiv.org/abs/2611.{i:05d}",
            source=("arxiv" if i % 3 == 0 else "github"),
            summary=f"abstract {i}",
            section_hint=(
                "tech_news"
                if i % 3 == 1
                else ("tools_releases" if i % 3 == 2 else None)
            ),
        )
        for i in range(9)
    ]
    monkeypatch.setattr(pipeline, "fetch_all", lambda client, cfg: (items, []))

    result = run_day(
        config,
        DATE,
        llm_client=FakeLlmClient(_mixed_selection(9)),
        summary_client=FakeLlmClient("garbage"),
        notify_fn=lambda *a, **k: None,
    )

    assert result.exit_code == 0
    html = result.digest_path.read_text(encoding="utf-8")
    assert html.count('class="section-summary"') == 3
    assert 'id="briefing"' not in html
    edition = load_edition(config.output_dir, DATE)
    assert edition is not None and len(edition.section_briefs) == 3


def test_shortfall_and_writer_partial_notices_coexist(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    config.llm.writer_v2 = True
    items = [
        make_item(
            id=f"arxiv:2611.{i:05d}",
            title=f"Notice story {i}",
            url=f"https://arxiv.org/abs/2611.{i:05d}",
            source="arxiv",
            summary=f"abstract {i}",
        )
        for i in range(9)
    ]
    monkeypatch.setattr(pipeline, "fetch_all", lambda client, cfg: (items, []))

    result = run_day(
        config,
        DATE,
        llm_client=FakeLlmClient(llm_ok_json(9)),
        summary_client=FakeLlmClient("garbage"),
        target=30,
        notify_fn=lambda *a, **k: None,
    )

    html = result.digest_path.read_text(encoding="utf-8")
    assert "9/30" in html
    assert t("vi", "writer_partial") in html
    assert t("vi", "notice_shortfall").format(actual=9, requested=30) in html


def test_old_snapshot_without_briefs_renders_legacy_rail(tmp_path):
    config = make_config(tmp_path)
    ranked = _mixed(6)
    points = ensure_coverage(parse_overview("Bài [[0]].", ranked), ranked)
    edition = Edition(
        date=DATE,
        locale="vi",
        ranked=tuple(ranked),
        mode="llm",
        model_name="old",
        overview="Legacy overview",
        overview_points=points,
    )
    save_edition(edition, config.output_dir)
    loaded = load_edition(config.output_dir, DATE)
    assert loaded is not None
    assert loaded.section_briefs == ()
    html = _render(
        tmp_path,
        list(loaded.ranked),
        overview=loaded.overview,
        overview_points=loaded.overview_points,
    )
    assert 'id="briefing"' in html
    assert 'class="overview-point' in html
    assert '<aside class="rail">' in html
    assert 'class="source-line"' in html


def test_section_briefs_keep_backfilled_flag_through_localize(tmp_path):
    from daily_digest.localize import localize_edition

    config = make_config(tmp_path)
    ranked = [
        RankedItem(
            item=make_item(
                id=f"arxiv:2611.{i:05d}",
                title=f"Localize story {i}",
                url=f"https://arxiv.org/abs/2611.{i:05d}",
                source="arxiv",
                summary=f"abstract {i}",
            ),
            why=f"why {i}",
            section="papers",
            backfilled=i == 0,
        )
        for i in range(4)
    ]
    edition = Edition(
        date=DATE,
        locale="vi",
        ranked=tuple(ranked),
        mode="llm",
        model_name="test",
        requested_count=30,
        backfilled_count=1,
    )
    from daily_digest.edition import render_edition, with_artifact

    html = render_edition(edition, config)
    path = config.output_dir / f"digest-{DATE}.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    save_edition(
        with_artifact(edition, path, html, config.output_dir), config.output_dir
    )

    item_payload = json.dumps(
        {
            "overview": "Localized overview",
            "items": [{"id": i, "summary": f"localized summary {i}"} for i in range(4)],
        }
    )
    brief_payload = json.dumps(
        {
            "sections": [
                {
                    "section": "papers",
                    "text": "localized brief [[0]] [[1]] [[2]] [[3]]",
                    "refs": [0, 1],
                }
            ]
        }
    )
    why_payload = json.dumps(
        {"items": [{"id": i, "why": f"localized why {i}"} for i in range(4)]}
    )
    result = localize_edition(
        config,
        DATE,
        "en",
        editor_client=FakeLlmClient(why_payload),
        writer_client=FakeLlmClient([item_payload, brief_payload]),
        backup=False,
    )

    assert result.exit_code == 0
    saved = load_edition(config.output_dir, DATE)
    assert saved is not None
    assert saved.ranked[0].backfilled is True
    assert saved.requested_count == 30 and saved.backfilled_count == 1
    assert saved.section_briefs
    assert saved.section_briefs[0].text.startswith("localized brief")
    assert saved.section_briefs[0].segments
    assert [item.item.id for item in saved.ranked] == [item.item.id for item in ranked]


def test_deadline_stops_writer_and_section_briefs_without_losing_page(tmp_path):
    config = make_config(tmp_path)
    ranked = _mixed(30)
    chat = FakeLlmClient("should not be called")

    assert (
        write_section_briefs(ranked, chat.chat, config, deadline=time.monotonic() - 1)
        == ()
    )
    assert chat.chat.calls == []

    with writer_deadline(time.monotonic() - 1):
        localized, overview = summarize_with_llm(ranked, chat.chat, config, locale="vi")
    assert chat.chat.calls == []
    assert overview == ""
    assert all(not item.llm_summary for item in localized)
    html = render_digest(
        localized,
        date=DATE,
        mode="llm",
        degraded=False,
        sources_failed=[],
        model_name="test",
        template=config.template_path,
        locale="vi",
    )
    assert "data-uid=" in html


def test_item_without_any_summary_renders_an_explicit_placeholder(tmp_path):
    ranked = [_item(i, "papers") for i in range(9)]
    ranked[0] = RankedItem(
        item=make_item(
            id="arxiv:2611.99999",
            title="No abstract",
            url="https://arxiv.org/abs/2611.99999",
            source="arxiv",
            summary="",
        ),
        why="why",
        section="papers",
        llm_summary="",
    )
    html = _render(tmp_path, ranked)
    assert t("vi", "summary_unavailable") in html


def test_heuristic_brief_uses_titles_not_raw_abstracts(tmp_path):
    ranked = [_item(i, "papers") for i in range(3)]
    brief = heuristic_section_briefs(ranked, make_config(tmp_path))[0]
    assert "Story 0" in brief.text
    assert "source summary 0" not in brief.text
    assert "llm summary 0" not in brief.text


def test_section_briefs_ja_accepts_native_and_rejects_english(tmp_path):
    config = make_config(tmp_path)
    ranked = _mixed(12)
    native_text = (
        "\u5177\u4f53\u7684\u306a\u7d50\u679c\u3092\u793a\u3059"
        "\u8981\u7d04\u3067\u3059\u3002\u624b\u6cd5\u3068\u6570"
        "\u5b57\u3092\u77ed\u304f\u307e\u3068\u3081\u307e\u3059\u3002"
    )
    native = json.dumps(
        {
            "sections": [
                {
                    "section": "papers",
                    "text": native_text + " [[0]] [[3]] [[6]] [[9]]",
                    "refs": [0, 3, 6],
                }
            ]
        }
    )
    briefs = write_section_briefs(
        ranked, FakeLlmClient(native).chat, config, locale="ja"
    )
    assert len(briefs) == 1
    assert "\u5177\u4f53\u7684\u306a\u7d50\u679c" in briefs[0].text

    english = json.dumps(
        {
            "sections": [
                {
                    "section": "papers",
                    "text": "This is English only text and should be rejected.",
                    "refs": [0],
                }
            ]
        }
    )
    rejected = write_section_briefs(
        ranked, FakeLlmClient(english).chat, config, locale="ja"
    )
    assert rejected == ()

    fallback = complete_section_briefs(rejected, ranked, config, "ja")
    assert len(fallback) == 3
    assert "\u3053\u306e\u30bb\u30af\u30b7\u30e7\u30f3" in fallback[0].text


def test_run_day_deadline_expiry_still_saves(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    items = [
        make_item(
            id=f"arxiv:2611.{i:05d}",
            title=f"Deadline story {i}",
            url=f"https://arxiv.org/abs/2611.{i:05d}",
            source=("arxiv" if i % 3 == 0 else "github"),
            summary=f"abstract {i}",
            section_hint=(
                "tech_news"
                if i % 3 == 1
                else ("tools_releases" if i % 3 == 2 else None)
            ),
        )
        for i in range(9)
    ]
    monkeypatch.setattr(pipeline, "fetch_all", lambda client, cfg: (items, []))
    monkeypatch.setattr(pipeline, "RUN_BUDGET_SECONDS", -1)
    writer = FakeLlmClient("SHOULD NOT BE CALLED")

    result = run_day(
        config,
        DATE,
        llm_client=FakeLlmClient(_mixed_selection(9)),
        summary_client=writer,
        notify_fn=lambda *a, **k: None,
    )

    assert result.exit_code == 0
    assert result.digest_path is not None and result.digest_path.exists()
    assert result.item_count == 9
    assert writer.chat.calls == []
    edition = load_edition(config.output_dir, DATE)
    assert edition is not None
    assert all(not item.llm_summary for item in edition.ranked)
    assert len(edition.section_briefs) == 3


def test_six_typographic_cover_modules_without_images(tmp_path):
    ranked = _mixed(30)
    html = _render(
        tmp_path,
        ranked,
        section_briefs=heuristic_section_briefs(ranked, make_config(tmp_path)),
    )
    assert html.count('story--typographic"') == 6
    assert html.count('class="story story--feature ') == 2
    assert html.count('class="story story--lead ') == 3
    assert "cover-pair" in html
    assert '<section class="most-read">' in html
    assert 'id="briefing"' not in html


def test_heuristic_brief_segments_cover_every_uid(tmp_path):
    ranked = _mixed(12)
    briefs = heuristic_section_briefs(ranked, make_config(tmp_path))
    for brief in briefs:
        item_uids = {r.item.id for r in ranked if r.section == brief.section}
        ref_uids = {s.ref.uid for s in brief.segments if s.ref is not None}
        assert ref_uids == item_uids
        assert brief.segments[0].text


def test_section_brief_preserves_paragraphs_and_rejects_partial(tmp_path):
    config = make_config(tmp_path)
    ranked = _mixed(12)
    payload = {
        "sections": [
            {
                "section": "papers",
                "text": "Doan mot [[0]] [[3]].\n\nDoan hai [[6]] [[9]].",
            }
        ]
    }
    briefs = write_section_briefs(
        ranked, FakeLlmClient(json.dumps(payload)).chat, config, locale="vi"
    )
    assert len(briefs) == 1
    assert "\n\n" in briefs[0].text
    assert len(briefs[0].segments) >= 4

    partial = {"sections": [{"section": "papers", "text": "Chi mot bai [[0]]."}]}
    rejected = write_section_briefs(
        ranked, FakeLlmClient(json.dumps(partial)).chat, config, locale="vi"
    )
    assert rejected == ()
    fallback = complete_section_briefs(rejected, ranked, config, "vi")
    assert len(fallback) == 3
    for brief in fallback:
        item_uids = {r.item.id for r in ranked if r.section == brief.section}
        ref_uids = {s.ref.uid for s in brief.segments if s.ref is not None}
        assert ref_uids == item_uids
