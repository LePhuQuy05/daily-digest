"""Hero cover regression tests: gate, markup, print, credit, contrast."""

from __future__ import annotations

from daily_digest.media import ImageAsset
from daily_digest.model import RankedItem
from daily_digest.render import render_digest
from daily_digest.util import PROJECT_ROOT
from helpers import make_config, make_item


def _ranked() -> list[RankedItem]:
    specs = (
        ("p0", "papers", "arxiv"),
        ("p1", "papers", "arxiv"),
        ("p2", "papers", "arxiv"),
        ("t0", "tech_news", "hn"),
        ("t1", "tech_news", "hn"),
    )
    return [
        RankedItem(
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
        for uid, section, source in specs
    ]


def _asset(
    uid: str,
    *,
    kind: str = "og",
    width: int = 1200,
    height: int = 630,
    credit: str | None = None,
    alt: str | None = None,
) -> ImageAsset:
    return ImageAsset(
        uid=uid,
        data_uri="data:image/jpeg;base64,AAAA",
        alt=alt or f"Alt {uid}",
        credit=credit if credit is not None else f"Hình: arXiv:{uid}",
        source_url=f"https://arxiv.org/abs/{uid}",
        kind=kind,
        width=width,
        height=height,
    )


def _render(tmp_path, images=None) -> str:
    config = make_config(tmp_path)
    return render_digest(
        _ranked(),
        date="2026-11-20",
        mode="llm",
        degraded=False,
        sources_failed=[],
        model_name="deepseek-v4.1-flash",
        template=config.template_path,
        overview="Tổng hợp hôm nay.",
        overview_label="Tổng hợp hôm nay",
        images=images,
    )


def _hero(html: str) -> str:
    start = html.index('<article class="story story--hero')
    end = html.index("</article>", start)
    return html[start:end]


def _css() -> str:
    return (PROJECT_ROOT / "templates" / "newsroom.css.j2").read_text(encoding="utf-8")


def _luminance(hex_color: str) -> float:
    def channel(value: str) -> float:
        c = int(value, 16) / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (hex_color[i : i + 2] for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def _contrast(fg: str, bg: str) -> float:
    hi, lo = max(_luminance(fg), _luminance(bg)), min(_luminance(fg), _luminance(bg))
    return (hi + 0.05) / (lo + 0.05)


def _composite(fg: str, alpha: float, bg: str = "#FFFFFF") -> str:
    fg_rgb = [int(fg[i : i + 2], 16) for i in (1, 3, 5)]
    bg_rgb = [int(bg[i : i + 2], 16) for i in (1, 3, 5)]
    mixed = [round(f * alpha + b * (1 - alpha)) for f, b in zip(fg_rgb, bg_rgb)]
    return "#" + "".join(f"{c:02X}" for c in mixed)


def test_og_landscape_hero_gets_cover(tmp_path):
    html = _render(
        tmp_path,
        images={"p0": _asset("p0"), "t0": _asset("t0")},
    )
    hero = _hero(html)

    assert html.count('story--cover"') == 1
    assert "story--cover" in hero
    assert "story-lede" in hero and "story-head" in hero
    assert '<p class="story-credit">Hình: arXiv:p0</p>' in hero
    assert 'loading="eager"' in hero
    assert 'fetchpriority="high"' in hero
    assert 'width="1200"' in hero and 'height="630"' in hero
    assert 'onerror="' in hero and "story--cover-failed" in hero
    assert html.count("<figcaption>") == 1  # the section lead keeps its caption
    assert html.count('data-uid="') == 5


def test_arxiv_portrait_square_and_missing_credit_do_not_get_cover(tmp_path):
    arxiv_hero = _hero(_render(tmp_path, images={"p0": _asset("p0", kind="arxiv_img")}))
    assert "story--cover" not in arxiv_hero
    assert "story--typographic" in arxiv_hero
    assert "<figcaption>" not in arxiv_hero

    for images in (
        {"p0": _asset("p0", width=800, height=1000)},
        {"p0": _asset("p0", width=1000, height=1000)},
    ):
        hero = _hero(_render(tmp_path, images=images))
        assert "story--cover" not in hero
        assert "<figcaption>" in hero  # normal hero keeps its credit

    no_credit = _hero(_render(tmp_path, images={"p0": _asset("p0", credit="")}))
    assert "story--cover" not in no_credit
    assert "<figcaption>" not in no_credit


def test_section_lead_og_is_not_a_cover(tmp_path):
    html = _render(
        tmp_path,
        images={"p0": _asset("p0", kind="arxiv_img"), "t0": _asset("t0")},
    )

    assert 'story--cover"' not in html
    assert "Hình: arXiv:t0" in html  # section lead still gets a normal caption


def test_missing_images_keep_the_text_hero(tmp_path):
    html = _render(tmp_path, images={})

    assert "story--hero" in html
    assert 'story--cover"' not in html
    assert '<figure class="story-media' not in html
    assert "Title p0" in html


def test_cover_credit_is_escaped_and_not_executable(tmp_path):
    html = _render(
        tmp_path,
        images={
            "p0": _asset(
                "p0",
                credit="Ảnh: <script>alert(1)</script>",
                alt='"><script>alert(2)</script>',
            )
        },
    )

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>alert(2)</script>" not in html
    assert 'class="story-credit"' in html


def test_cover_css_is_transparent_16_9_and_print_safe():
    css = _css()

    assert ".story--cover .story-lede" in css
    assert "height: auto" in css
    assert "aspect-ratio: 16 / 9" in css
    assert "background: color-mix(in srgb, var(--cover-bg) 70%, transparent)" in css
    assert "94%" not in css
    assert ".story--cover .story-head" in css
    assert "margin: -72px 0 0" in css
    assert ".story--cover-failed .story-media" in css
    assert "linear-gradient" not in css

    print_block = css.split("@media print", 1)[1]
    assert ".story--cover .story-head { position: static" in print_block
    assert "background: none" in print_block
    assert ".story--cover .story-head .story-credit" in print_block
    assert "font-size: 7.5pt" in print_block


def test_cover_text_contrast_over_a_white_image():
    panel = _composite("#141210", 0.70)
    assert _contrast("#FBFAF7", panel) >= 4.5
    assert _contrast("#D8D2C8", panel) >= 4.5
    assert _contrast("#FBFAF7", panel) >= 3.0  # large title
