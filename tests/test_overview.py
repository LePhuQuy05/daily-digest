"""Overview parser, labels, coverage and heuristic fallback."""

from __future__ import annotations

from daily_digest.model import RankedItem
from daily_digest.overview import (
    REST_TEXT,
    ensure_coverage,
    heuristic_overview_points,
    parse_overview,
    short_label,
)
from helpers import make_config, make_item


def _ranked(count: int = 4) -> list[RankedItem]:
    sections = ("papers", "tech_news", "tools_releases")
    return [
        RankedItem(
            item=make_item(
                id=f"arxiv:2611.{i:05d}",
                title=f"Paper {i}: A useful title",
                url=f"https://arxiv.org/abs/2611.{i:05d}",
                source="arxiv",
            ),
            why=f"why {i}",
            section=sections[i % len(sections)],
        )
        for i in range(count)
    ]


def _uids(points) -> set[str]:
    return {
        segment.ref.uid
        for point in points
        for segment in point.segments
        if segment.ref is not None
    }


def test_parse_markers_into_inline_refs_and_takeaway():
    ranked = _ranked()
    points = parse_overview(
        "Hôm nay [[0]] và [[1]] cho thấy hướng mới.\n\n"
        "Điểm cần nhớ: [[2]] là đáng đọc nhất.",
        ranked,
    )

    assert [point.kind for point in points] == ["theme", "takeaway"]
    first = points[0]
    assert any(
        segment.ref and segment.ref.uid == ranked[0].item.id
        for segment in first.segments
    )
    assert any(
        segment.ref and segment.ref.uid == ranked[1].item.id
        for segment in first.segments
    )
    assert "[[0]]" not in "".join(
        segment.text for point in points for segment in point.segments
    )


def test_invalid_and_duplicate_markers_are_dropped():
    ranked = _ranked()
    points = parse_overview(
        "A [[99]] B [[x]] C [[0]] [[0]] D.",
        ranked,
    )

    text = "".join(segment.text for segment in points[0].segments)
    assert "[[" not in text
    assert "A" in text and "B" in text and "C" in text and "D" in text
    refs = [segment.ref.uid for segment in points[0].segments if segment.ref]
    assert refs == [ranked[0].item.id]


def test_marker_at_start_and_end_is_clean():
    ranked = _ranked()
    points = parse_overview("[[0]] ở đầu và cuối [[1]]", ranked)

    text = "".join(segment.text for segment in points[0].segments)
    assert "[[" not in text
    assert [s.ref.uid for s in points[0].segments if s.ref] == [
        ranked[0].item.id,
        ranked[1].item.id,
    ]


def test_no_markers_keeps_plain_text_points():
    points = parse_overview("Một câu bình thường.\n\nMột câu khác.", _ranked())
    assert len(points) == 2
    assert all(point.segments[0].ref is None for point in points)


def test_more_than_five_points_keeps_first_four_and_last():
    text = "First.\nSecond.\nThird.\nFourth.\nFifth.\nSixth."
    points = parse_overview(text, _ranked())
    assert len(points) == 5
    assert points[-1].kind == "takeaway"
    assert "Sixth" in "".join(segment.text for segment in points[-1].segments)


def test_duplicate_title_before_marker_is_removed_once():
    ranked = _ranked()
    ranked = [
        RankedItem(
            item=make_item(
                id="arxiv:2611.99999",
                title="GUARD: Stabilizing Recursive Self-Improvement",
                url="https://arxiv.org/abs/2611.99999",
                source="arxiv",
            ),
            why="why",
            section="papers",
        )
    ]
    points = parse_overview("A GUARD [[0]] dùng directional regret.", ranked)

    text = "".join(segment.text for segment in points[0].segments)
    assert "GUARD" not in text  # the chip supplies the title
    assert any(
        segment.ref and segment.ref.label == "GUARD" for segment in points[0].segments
    )


def test_short_label_cases():
    assert short_label("QDA: Closed-Loop LLM Quantization", 1) == "QDA"
    assert short_label("", 7) == "Bài 7"
    long = "A very long title that has no colon and keeps going past the label cap"
    label = short_label(long, 2)
    assert len(label) <= 28
    assert label.endswith("…")
    assert "arxiv:" not in short_label("arxiv:2611.1", 1)


def test_ensure_coverage_adds_rest_before_takeaway():
    ranked = _ranked()
    points = parse_overview(
        "Bài [[0]] và [[1]].\n\nĐiểm cần nhớ: [[2]].",
        ranked,
    )
    assert _uids(points) == {r.item.id for r in ranked[:3]}

    covered = ensure_coverage(points, ranked)

    assert [point.kind for point in covered] == ["theme", "rest", "takeaway"]
    assert _uids(covered) == {r.item.id for r in ranked}
    rest = covered[1]
    assert any(segment.text.startswith(REST_TEXT.strip()) for segment in rest.segments)


def test_ensure_coverage_with_no_points_references_everything():
    ranked = _ranked(3)
    covered = ensure_coverage((), ranked)
    assert len(covered) == 1
    assert covered[0].kind == "rest"
    assert _uids(covered) == {r.item.id for r in ranked}


def test_ensure_coverage_is_idempotent_when_complete():
    ranked = _ranked(3)
    points = parse_overview("[[0]] [[1]] [[2]]", ranked)
    covered = ensure_coverage(points, ranked)
    assert covered == points


def test_heuristic_overview_covers_every_section_item(tmp_path):
    ranked = _ranked(6)
    points = heuristic_overview_points(ranked, make_config(tmp_path))

    assert points
    assert _uids(points) == {r.item.id for r in ranked}
    text = " ".join(segment.text for point in points for segment in point.segments)
    assert "Research Papers" in text
    assert "Tech News" in text
    assert "Tools & Releases" in text


def test_thirty_item_overview_keeps_full_coverage_and_scales_budget():
    from daily_digest.ranking.llm import overview_char_budget

    ranked = _ranked(30)
    points = ensure_coverage(
        parse_overview(" ".join(f"[[{i}]]" for i in range(20)), ranked),
        ranked,
    )

    assert _uids(points) == {r.item.id for r in ranked}
    assert any(point.kind == "rest" for point in points)
    assert overview_char_budget(30) == 2680
