"""Unit tests for the article-image pipeline (no network, no Edge)."""

from __future__ import annotations

import io
import json
import socket

import pytest
from PIL import Image

from daily_digest.media import (
    Candidate,
    ImageAsset,
    _assert_public_url,
    _arxiv_candidates,
    _og_from_html,
    _prepare_candidate,
    _review_image,
    collect_images,
)
from daily_digest.model import RankedItem
from helpers import make_config, make_item


def _jpeg(width=400, height=240):
    img = Image.new("RGB", (width, height), (180, 40, 60))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def _item(uid: str, section: str, source: str = "arxiv") -> RankedItem:
    return RankedItem(
        item=make_item(
            id=uid,
            title=f"Title {uid}",
            url=f"https://example.test/{uid}",
            source=source,
        ),
        why=f"why {uid}",
        section=section,  # type: ignore[arg-type]
        llm_summary=f"summary {uid}",
    )


def _real_mix():
    return [_item(f"p{i}", "papers") for i in range(11)] + [
        _item("t0", "tech_news", "hn")
    ]


class TestParsers:
    def test_og_good_and_rejected(self):
        good = _og_from_html(
            '<meta property="og:image" content="/hero.jpg">',
            "https://news.example/story",
            "A story",
        )
        assert len(good) == 1
        assert good[0].image_urls == ("https://news.example/hero.jpg",)
        assert good[0].credit.startswith("Ảnh: news.example")

        for bad in (
            "https://arxiv.org/static/browse/0.3.4/images/arxiv-logo-fb.png",
            "https://cdn-thumbnails.huggingface.co/social-thumbnails/papers/1.png",
            "https://opengraph.githubassets.com/1/a/b",
        ):
            html = f'<meta property="og:image" content="{bad}">'
            assert _og_from_html(html, "https://x.test", "t") == []

    def test_arxiv_object_figure_is_supported(self):
        html = """
        <figure class="ltx_figure">
          <object type="image/svg+xml" data="2611.1234v1/fig.svg"></object>
          <figcaption>Figure 1: object figure</figcaption>
        </figure>
        """
        candidates = _arxiv_candidates(
            html, "https://arxiv.org/html/2611.1234", "Title", "2611.1234"
        )
        assert len(candidates) == 1
        assert candidates[0].kind == "arxiv_svg"
        assert candidates[0].svg_url == "https://arxiv.org/html/2611.1234v1/fig.svg"

    def test_arxiv_first_figure_skips_tables_and_data(self):
        html = """
        <style>.ltx_figure{color:red}</style>
        <figure class="ltx_figure"><img src="2611.1234v1/fig.png"><figcaption>Figure 1: real</figcaption></figure>
        <figure class="ltx_table"><img src="2611.1234v1/table.png"></figure>
        <figure class="ltx_figure"><img src="data:image/png;base64,AAAA"><svg viewBox="0 0 10 10"><path d="M0 0"/></svg></figure>
        """
        candidates = _arxiv_candidates(
            html, "https://arxiv.org/html/2611.1234", "Title", "2611.1234"
        )
        assert len(candidates) == 2
        assert candidates[0].kind == "arxiv_img"
        assert "https://arxiv.org/html/2611.1234v1/fig.png" in candidates[0].image_urls
        assert candidates[1].kind == "arxiv_svg"
        assert "Figure 1" in candidates[0].alt
        assert "ltx_table" not in candidates[0].svg_html.lower()


class TestSafety:
    def test_private_and_non_http_urls_are_blocked(self):
        for url in (
            "http://127.0.0.1/a.png",
            "http://localhost/a.png",
            "file:///a.png",
        ):
            with pytest.raises(ValueError):
                _assert_public_url(url)

    def test_public_ip_allowed(self, monkeypatch):
        monkeypatch.setattr(
            socket,
            "getaddrinfo",
            lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))],
        )
        _assert_public_url("https://example.com/a.png")


class TestReview:
    def test_suitable_and_rejected_json(self):
        assert (
            _review_image(
                lambda m: '{"suitable": true, "kind": "figure"}', _jpeg(), "t", ""
            )
            is True
        )
        assert (
            _review_image(
                lambda m: '{"suitable": false, "reason": "logo"}', _jpeg(), "t", ""
            )
            is False
        )

    def test_invalid_or_failed_review_accepts(self):
        assert _review_image(lambda m: "not json", _jpeg(), "t", "") is True
        assert (
            _review_image(
                lambda m: (_ for _ in ()).throw(RuntimeError("offline")),
                _jpeg(),
                "t",
                "",
            )
            is True
        )


class TestPrepareAndCache:
    def test_prepare_caches_and_returns_data_uri(self, tmp_path, monkeypatch):
        config = make_config(tmp_path)
        config.media.enabled = True
        config.media.cache_dir = str(tmp_path / "media")
        config.media.llm_review = False

        candidate = Candidate(
            kind="og",
            source_url="https://news.example/story",
            alt="Story image",
            credit="Ảnh: news.example",
            image_urls=("https://news.example/hero.jpg",),
        )
        monkeypatch.setattr(
            "daily_digest.media._download_image",
            lambda *a, **k: (_jpeg(), 400, 240),
        )
        asset = _prepare_candidate(candidate, None, config, None, "Story")
        assert asset is not None
        assert asset.data_uri.startswith("data:image/jpeg;base64,")
        assert asset.kind == "og"
        assert list((tmp_path / "media").glob("*.jpg"))

        # second call must use the cache, not the downloader
        monkeypatch.setattr(
            "daily_digest.media._download_image",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("network call")),
        )
        again = _prepare_candidate(candidate, None, config, None, "Story")
        assert again is not None
        assert again.data_uri == asset.data_uri

    def test_svg_without_edge_returns_none(self, tmp_path, monkeypatch):
        from daily_digest.media import _rasterize_svg

        monkeypatch.setattr("daily_digest.media._find_edge", lambda: None)
        candidate = Candidate(
            kind="arxiv_svg",
            source_url="https://arxiv.org/html/1",
            alt="Figure",
            credit="Hình: arXiv:1",
            svg_html="<figure class='ltx_figure'><svg></svg></figure>",
            base_url="https://arxiv.org/html/1",
        )
        assert _rasterize_svg(candidate, 1180) is None


class TestCollectTargets:
    def test_only_hero_and_section_leads(self, tmp_path, monkeypatch):
        config = make_config(tmp_path)
        config.media.enabled = True
        config.media.llm_review = False
        seen: list[str] = []

        def fake_candidates(item, client, cfg):
            seen.append(item.item.id)
            return [
                Candidate(
                    kind="og",
                    source_url=f"https://x.test/{item.item.id}",
                    alt="alt",
                    credit="Ảnh: x.test",
                    image_urls=("https://x.test/img.jpg",),
                )
            ]

        monkeypatch.setattr("daily_digest.media._candidates_for", fake_candidates)
        monkeypatch.setattr(
            "daily_digest.media._prepare_candidate",
            lambda candidate, client, cfg, chat, title: ImageAsset(
                uid="",
                data_uri="data:image/jpeg;base64,AAAA",
                alt=candidate.alt,
                credit=candidate.credit,
                source_url=candidate.source_url,
                kind=candidate.kind,
                width=400,
                height=240,
            ),
        )
        assets = collect_images(_real_mix(), config, chat=None)
        # hero p0 + papers lead p2 + tech lead t0; secondary p1 is excluded
        assert set(assets) == {"p0", "p2", "t0"}
        assert "p1" not in assets
        assert set(seen) == {"p0", "p2", "t0"}

    def test_max_images_cap(self, tmp_path, monkeypatch):
        config = make_config(tmp_path)
        config.media.enabled = True
        config.media.llm_review = False
        config.media.max_images = 2
        monkeypatch.setattr(
            "daily_digest.media._candidates_for",
            lambda item, client, cfg: [
                Candidate(
                    kind="og",
                    source_url="https://x.test/a",
                    alt="a",
                    credit="Ảnh: x.test",
                    image_urls=("https://x.test/a.jpg",),
                )
            ],
        )
        monkeypatch.setattr(
            "daily_digest.media._prepare_candidate",
            lambda *a, **k: ImageAsset(
                uid="",
                data_uri="data:image/jpeg;base64,AAAA",
                alt="a",
                credit="Ảnh: x.test",
                source_url="https://x.test/a",
                kind="og",
                width=400,
                height=240,
            ),
        )
        assert len(collect_images(_real_mix(), config, chat=None)) == 2
