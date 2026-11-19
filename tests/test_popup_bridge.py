"""Digest-data blob: render <-> extract roundtrip, hostile titles, tolerance."""

from daily_digest.model import RankedItem
from daily_digest.popup_bridge import extract_digest_data
from daily_digest.render import build_digest_data, render_digest, write_digest
from helpers import make_config, make_item


def _render(tmp_path, ranked, date="2026-11-19"):
    config = make_config(tmp_path)
    data = build_digest_data(ranked, [], date)
    html = render_digest(
        ranked,
        date=date,
        mode="llm",
        degraded=False,
        sources_failed=[],
        model_name="glm-5.3",
        template=config.template_path,
        digest_data=data,
    )
    return html, data


def test_blob_roundtrip_through_real_template(tmp_path):
    ranked = [
        RankedItem(
            item=make_item(
                id="hn:1",
                title="Normal title",
                url="https://x.io/1",
                source="hn",
                points=42,
                summary="an abstract",
            ),
            why="why",
            section="tech_news",
        )
    ]
    html, data = _render(tmp_path, ranked)
    assert '<script type="application/json" id="digest-data">' in html
    extracted = extract_digest_data(html)
    assert extracted == data
    assert extracted["date"] == "2026-11-19"
    assert extracted["items"]["hn:1"]["title"] == "Normal title"
    assert extracted["items"]["hn:1"]["points"] == 42


def test_blob_survives_hostile_titles(tmp_path):
    hostile = [
        "</script><script>alert(1)",
        "weird {braces} and }{ chars",
        "emoji 📡 and unicode — em-dash",
        'title\nwith\nnewlines and  "quotes"',
    ]
    ranked = [
        RankedItem(
            item=make_item(
                id=f"hn:{i}", title=title, url=f"https://x.io/{i}", source="hn"
            ),
            why=f"w{i}",
            section="tech_news",
        )
        for i, title in enumerate(hostile)
    ]
    html, data = _render(tmp_path, ranked)
    # no literal </script> can appear inside the blob (tojson escapes < as \u003c)
    blob_start = html.index('id="digest-data">') + len('id="digest-data">')
    blob_end = html.index("</script>", blob_start)
    assert "</script>" not in html[blob_start:blob_end]
    extracted = extract_digest_data(html)
    assert extracted == data
    for i, title in enumerate(hostile):
        assert (
            extracted["items"][f"hn:{i}"]["title"] == title
        )  # original survives roundtrip


def test_latest_html_self_pairs(tmp_path):
    ranked = [
        RankedItem(
            item=make_item(id="hn:1", title="T", url="https://x.io/1", source="hn"),
            why="w",
            section="tech_news",
        )
    ]
    html, _ = _render(tmp_path, ranked)
    path = write_digest(html, tmp_path, "2026-11-19")
    latest = tmp_path / "latest.html"
    # latest.html is the same html: extraction works without any filename date
    assert (
        extract_digest_data(latest.read_text(encoding="utf-8"))["date"] == "2026-11-19"
    )


def test_extract_tolerant_on_old_and_corrupt_html():
    assert extract_digest_data("<html><body>old digest, no blob</body></html>") == {}
    assert (
        extract_digest_data(
            '<script type="application/json" id="digest-data">{not json</script>'
        )
        == {}
    )
    assert (
        extract_digest_data(
            '<script type="application/json" id="digest-data">["a list"]</script>'
        )
        == {}
    )  # non-dict payload
    # attribute order must not matter (the regex tolerates any attribute layout)
    assert extract_digest_data(
        '<script id="digest-data" type="application/json">{"date": "2026-11-19", "items": {}}</script>'
    ) == {"date": "2026-11-19", "items": {}}


def test_bridge_only_css_hidden_by_default(tmp_path):
    ranked = [
        RankedItem(
            item=make_item(id="hn:1", title="T", url="https://x.io/1", source="hn"),
            why="w",
            section="tech_news",
        )
    ]
    html, _ = _render(tmp_path, ranked)
    assert ".bridge-only { display: none; }" in html
    assert "body.bridged .bridge-only" in html
    assert "pywebviewready" in html  # the reveal listener exists
    assert "typeof window.pywebview.api.feedback" in html  # guarded by api presence


def test_saved_review_ui_and_bridge_calls_are_present(tmp_path):
    ranked = [
        RankedItem(
            item=make_item(id="hn:1", title="T", url="https://x.io/1", source="hn"),
            why="w",
            section="tech_news",
        )
    ]
    html, _ = _render(tmp_path, ranked)

    for needle in (
        'id="saved-open"',
        'id="refresh-now"',
        'id="saved-modal"',
        'id="saved-list"',
        'id="undo-bar"',
        'id="undo-btn"',
        "pywebview.api.saved_items()",
        "pywebview.api.refresh()",
        "pywebview.api.ratings()",
        "pywebview.api.undo_unsave(uid)",
        "pywebview.api.toggle_save(parts[0])",
        "applySaved",
        "data-saved",
        "Đã lưu",
        "Tìm bài mới",
        "data-feedback",
        ".act.active",
    ):
        assert needle in html


def test_digest_data_omitted_when_none(tmp_path):
    config = make_config(tmp_path)
    html = render_digest(
        [],
        date="2026-11-19",
        mode="llm",
        degraded=False,
        sources_failed=[],
        model_name="glm-5.3",
        template=config.template_path,
    )
    assert 'id="digest-data"' not in html  # old-style render (tests, backcompat)
