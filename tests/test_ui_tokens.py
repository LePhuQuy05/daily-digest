"""UI redesign ("Editorial Dark Reading Room") — template assertions per docs/ui-redesign-plan.md.

Step 1: token layer + dark default + light override + theme toggle.
(Later steps append their own test classes here.)"""

import re

from daily_digest.model import RankedItem
from daily_digest.render import render_digest
from helpers import make_config, make_item


def _css():
    from daily_digest.util import PROJECT_ROOT

    return (PROJECT_ROOT / "templates" / "newsroom.css.j2").read_text(encoding="utf-8")


def _partial():
    from daily_digest.util import PROJECT_ROOT

    return (PROJECT_ROOT / "templates" / "partials" / "_story.html.j2").read_text(
        encoding="utf-8"
    )


def _html(tmp_path, **extra):
    config = make_config(tmp_path)
    ranked = [
        RankedItem(
            item=make_item(
                id="hn:1",
                title="LLM paper",
                url="https://x.io/1",
                source="hn",
                points=42,
            ),
            why="why line",
            section="tech_news",
        )
    ]
    return render_digest(
        ranked,
        date="2026-11-19",
        mode="llm",
        degraded=False,
        sources_failed=[],
        model_name="glm-5.3",
        template=config.template_path,
        overview="Tổng hợp hôm nay về agents.",
        overview_label="Tổng hợp hôm nay",
        **extra,
    )


class TestNewsroomShell:
    @staticmethod
    def _template():
        from daily_digest.util import PROJECT_ROOT

        return (PROJECT_ROOT / "templates" / "digest.html.j2").read_text(
            encoding="utf-8"
        )

    def test_h1_and_titles_are_serif(self, tmp_path):
        html = _html(tmp_path)
        h1_rule = re.search(r"h1 \{[^}]*\}", html).group(0)
        assert "var(--font-serif)" in h1_rule
        title_rule = re.search(r"\.story-title \{[^}]*\}", html).group(0)
        assert "var(--font-serif)" in title_rule

    def test_section_nav_is_sticky(self, tmp_path):
        html = _html(tmp_path)
        nav_rule = re.search(r"\.section-nav \{[^}]*\}", html).group(0)
        assert "position: sticky" in nav_rule
        assert "top: 0" in nav_rule
        assert "backdrop-filter" not in nav_rule

    def test_dateline_uses_sans_caps(self, tmp_path):
        html = _html(tmp_path)
        date_rule = re.search(r"\.dateline \{[^}]*\}", html).group(0)
        assert "var(--font-sans)" in date_rule
        assert "text-transform: uppercase" in date_rule
        assert "THỨ NĂM, 19.11.2026" in html

    def test_overview_no_newspaper_drop_cap(self, tmp_path):
        """The drop-cap split Vietnamese words ('H | ôm') — it must stay removed."""
        html = _html(tmp_path)
        assert ".overview p::first-letter" not in html  # drop-cap is gone
        assert "::first-letter" not in html

    def test_overview_is_scannable_bullets(self, tmp_path):
        html = _html(tmp_path)
        assert ".overview-points" in html
        assert 'class="overview-point' in html
        partial = _partial()
        assert "points[:3] + points[-1:]" in partial  # cap, but keep the takeaway
        assert "spotlight" in partial  # last (takeaway) bullet highlighted

    def test_briefing_is_news_box_not_gradient(self, tmp_path):
        html = _html(tmp_path)
        overview_rule = re.search(r"\.overview\.briefing \{[^}]*\}", html).group(0)
        assert "var(--paper-warm)" in overview_rule
        assert "border-top: 3px solid var(--red)" in overview_rule
        assert "linear-gradient" not in html
        assert "shimmer" not in html
        assert "TỔNG HỢP HÔM NAY" in html  # kicker from overview_label
        assert "Trong ngày" in html

    def test_overview_line_height_reading(self, tmp_path):
        html = _html(tmp_path)
        point_rule = re.search(r"\.overview-point \{[^}]*\}", html).group(0)
        assert "1.6" in point_rule  # relaxed reading rhythm

    def test_overview_spotlight_uses_arrow_not_bullet(self, tmp_path):
        html = _html(tmp_path)
        spotlight = re.search(
            r"\.overview-point\.spotlight::before \{[^}]*\}", html
        ).group(0)
        assert 'content: "→"' in spotlight  # callout, not a boxed bullet
        assert "background: none" in spotlight


class TestNewsroomSectionFronts:
    @staticmethod
    def _template():
        from daily_digest.util import PROJECT_ROOT

        return (PROJECT_ROOT / "templates" / "digest.html.j2").read_text(
            encoding="utf-8"
        )

    def test_section_identity_classes_and_vars(self, tmp_path):
        html = _html(tmp_path)
        tpl = self._template()
        assert (
            "sec-papers" in html
            and "sec-tech_news" in html
            and "sec-tools_releases" in html
        )
        assert ".sec-papers { --section-color: var(--section-papers); }" in html
        assert "sec-{{ section_key }}" in tpl  # template binds the class dynamically

    def test_section_header_has_numbered_index(self, tmp_path):
        tpl = self._template()
        css = _css()
        assert ".idx" in css  # CSS moved to newsroom.css.j2 at P2a
        assert '"%02d" | format(loop.index)' in tpl

    def test_story_has_no_card_chrome(self, tmp_path):
        html = _html(tmp_path)
        story_rule = re.search(r"\.story \{[^}]*\}", html).group(0)
        assert "box-shadow" not in story_rule
        assert "border-radius" not in story_rule
        assert "background" not in story_rule

    def test_no_shimmer_or_stagger(self, tmp_path):
        html = _html(tmp_path)
        assert "shimmer" not in html
        assert "@keyframes rise" not in html
        assert "prefers-reduced-motion: reduce" in html
        reduced = html.split("prefers-reduced-motion: reduce", 1)[1][:120]
        assert "animation: none" in reduced

    def test_meta_is_text_not_chips(self, tmp_path):
        partial = _partial()
        assert '<div class="meta">' in partial
        assert 'class="chip"' not in partial

    def test_pinned_section_keeps_test_locked_class(self):
        partial = _partial()
        assert 'class="block pinned-block"' in partial  # locked by test_feedback


class TestStep4IconsStates:
    @staticmethod
    def _template():
        from daily_digest.util import PROJECT_ROOT

        return (PROJECT_ROOT / "templates" / "digest.html.j2").read_text(
            encoding="utf-8"
        )

    def test_no_emoji_icons_in_template(self, tmp_path):
        tpl = self._template()
        for emoji in ("👍", "👎", "🔖", "📌", "✓"):
            assert emoji not in tpl, f"emoji icon {emoji} must be SVG now"

    def test_svg_symbol_defs_exist(self, tmp_path):
        html = _html(tmp_path)
        for symbol in (
            "i-thumb-up",
            "i-thumb-down",
            "i-bookmark",
            "i-pin",
            "i-check",
            "i-send",
            "i-moon",
            "i-sun",
        ):
            assert f'id="{symbol}"' in html, f"missing SVG symbol {symbol}"

    def test_buttons_use_svg_and_aria_labels(self, tmp_path):
        tpl = _partial()
        assert '<use href="#i-thumb-up"/>' in tpl
        assert '<use href="#i-thumb-down"/>' in tpl
        assert '<use href="#i-bookmark"/>' in tpl
        assert 'aria-label="Thích mục này"' in tpl
        assert 'aria-label="Lưu mục này vào Nhìn lại"' in tpl
        assert 'aria-label="Hỏi về mục này"' in tpl
        assert 'aria-live="polite"' in tpl  # ask answers announced politely

    def test_act_buttons_have_cursor_pointer_and_min_size(self, tmp_path):
        html = _html(tmp_path)
        act_rule = re.search(r"\.act \{[^}]*\}", html).group(0)
        assert "cursor: pointer" in act_rule
        assert "min-width: 32px" in act_rule and "height: 32px" in act_rule
        assert "display: inline-flex" in act_rule

    def test_buttons_have_a_pressed_tactile_state(self, tmp_path):
        html = _html(tmp_path)
        assert ".act:active:not(:disabled)" in html
        assert "scale(0.97)" in html
        assert "box-shadow: inset" in html
        assert "prefers-reduced-motion: reduce" in html

    def test_feedback_states_are_high_contrast(self, tmp_path):
        html = _html(tmp_path)
        done_rule = re.search(r"\.act\.done \{[^}]*\}", html).group(0)
        assert "background: var(--accent)" in done_rule  # solid fill, not outline-only
        assert "color: #ffffff" in done_rule
        failed_rule = re.search(r"\.act\.failed \{[^}]*\}", html).group(0)
        assert "var(--danger)" in failed_rule

    def test_ask_row_is_inline(self, tmp_path):
        html = _html(tmp_path)
        assert "body.bridged .ask { display: block" in html
        row_rule = re.search(r"\.ask-row \{[^}]*\}", html).group(0)
        assert "display: flex" in row_rule
        input_rule = re.search(r"\.ask-input \{[^}]*\}", html).group(0)
        assert "flex: 1 1 55%" in input_rule  # input + button share one row

    def test_ask_is_native_details(self):
        partial = _partial()
        assert '<details class="ask">' in partial
        assert "<summary>Hỏi biên tập</summary>" in partial

    def test_nav_active_observer(self):
        tpl = self._template()
        assert "IntersectionObserver" in tpl
        assert "aria-current" in tpl
        assert "section-nav-indicator" in tpl
        assert "moveIndicator" in tpl
        assert "offsetLeft" in tpl
        assert "scrollIntoView" in tpl

    def test_nav_scrolls_smoothly_to_sections(self, tmp_path):
        html = _html(tmp_path)
        assert "scroll-behavior: smooth" in html
        assert "scroll-margin-top: 56px" in html
        assert 'behavior: reduce ? "auto" : "smooth"' in html

    def test_theme_toggle_icon_swaps_by_theme(self, tmp_path):
        html = _html(tmp_path)
        css = _css()
        assert 'class="icon icon-moon"' in html and 'class="icon icon-sun"' in html
        assert ".icon-sun { display: inline; }" in css  # light is the default
        assert '[data-theme="dark"] .icon-sun { display: none; }' in css
        assert '[data-theme="dark"] .icon-moon { display: inline; }' in css

    def test_typing_dots_animation(self, tmp_path):
        html = _html(tmp_path)
        assert ".dots" in html and "@keyframes blink" in html
        tpl = self._template()
        assert 'out.innerHTML = \'<span class="dots">' in tpl  # JS swaps text for dots
        reduced = html.split("prefers-reduced-motion: reduce", 1)[1]
        assert (
            "animation: none" in reduced
        )  # card reveal; dots keep tiny pulse (non-essential)

    def test_focus_visible_ring(self, tmp_path):
        html = _html(tmp_path)
        assert ":focus-visible" in html
        assert "outline: 2px solid var(--ring)" in html


class TestStep5PrintPolish:
    @staticmethod
    def _template():
        from daily_digest.util import PROJECT_ROOT

        return (PROJECT_ROOT / "templates" / "digest.html.j2").read_text(
            encoding="utf-8"
        )

    def test_print_css_exists_and_hides_interactive(self, tmp_path):
        html = _html(tmp_path)
        assert "@media print" in html
        print_block = html.split("@media print", 1)[1]
        assert (
            ".theme-toggle" in print_block and "display: none !important" in print_block
        )
        assert "break-inside: avoid" in print_block

    def test_print_is_a4_two_column_broadsheet(self):
        css = _css()
        assert "@page { size: A4; margin: 16mm; }" in css
        print_block = css.split("@media print", 1)[1]
        assert ".section-nav" in print_block and ".most-read" in print_block
        assert "--paper: #FFFFFF" in print_block
        assert "column-count: 2" in print_block
        assert "break-after: avoid" in print_block

    def test_empty_state_renders_for_empty_sections(self, tmp_path):
        html = _html(tmp_path)  # 1 tech_news item -> papers/tools empty
        assert "hôm nay không có mục nào" in html
        assert html.count("empty") >= 2  # two empty sections

    # ---------- contrast audit (WCAG 2.1 relative luminance, >= 4.5:1) ----------

    @staticmethod
    def _luminance(hex_color: str) -> float:
        def channel(value: str) -> float:
            c = int(value, 16) / 255.0
            return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

        r, g, b = (hex_color[i : i + 2] for i in (1, 3, 5))
        return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)

    @classmethod
    def _contrast(cls, fg: str, bg: str) -> float:
        l1, l2 = cls._luminance(fg), cls._luminance(bg)
        hi, lo = max(l1, l2), min(l1, l2)
        return (hi + 0.05) / (lo + 0.05)

    def test_dark_theme_contrast_audit(self):
        pairs = [
            ("#F2EFE9", "#121212", "text-1 on bg"),
            ("#C9C4BC", "#121212", "text-2 on card"),
            ("#9A958D", "#121212", "text-3 on bg"),
            ("#FF6B6B", "#121212", "red on bg"),
            ("#8CC8FF", "#121212", "link on bg"),
        ]
        for fg, bg, label in pairs:
            ratio = self._contrast(fg, bg)
            assert ratio >= 4.5, f"night: {label} = {ratio:.2f}:1 (< 4.5)"

    def test_light_theme_contrast_audit(self):
        pairs = [
            ("#1A1A1A", "#FBFAF7", "text-1 on paper"),
            ("#4F4F4F", "#FBFAF7", "text-2 on paper"),
            ("#6B6B6B", "#FBFAF7", "text-3 on paper"),
            ("#9F224E", "#FBFAF7", "red on paper"),
            ("#1A4F8B", "#FBFAF7", "link on paper"),
            ("#B91C1C", "#FBFAF7", "danger on paper"),
        ]
        for fg, bg, label in pairs:
            ratio = self._contrast(fg, bg)
            assert ratio >= 4.5, f"light: {label} = {ratio:.2f}:1 (< 4.5)"

    def test_light_tokens_match_audited_values(self):
        css = _css()
        for audited in (
            "--paper: #FBFAF7",
            "--red: #9F224E",
            "--ink-3: #6B6B6B",
            "--danger-ink: #B91C1C",
        ):
            assert audited in css, f"token drifted from audit: {audited}"


class TestStep1Tokens:
    def test_token_layer_present(self, tmp_path):
        html = _html(tmp_path)
        assert ":root {" in html
        for token in (
            "--bg:",
            "--bg-raised:",
            "--text-1:",
            "--text-2:",
            "--accent:",
            "--accent-soft:",
            "--link:",
            "--border:",
            "--section-papers:",
            "--section-news:",
            "--section-tools:",
            "--card-radius:",
        ):
            assert token in html, f"missing token {token}"

    def test_light_is_default_and_dark_overrides_exist(self, tmp_path):
        html = _html(tmp_path)
        css = _css()
        root = css.split(":root {", 1)[1].split("}", 1)[0]
        assert "--paper: #FBFAF7;" in root  # light newsprint default
        assert '[data-theme="dark"]' in css  # explicit night edition
        assert "@media (prefers-color-scheme" not in css  # no auto switching

    def test_component_styles_use_tokens_not_raw_hex(self, tmp_path):
        html = _html(tmp_path)
        body_rule = re.search(r"body \{[^}]*\}", html).group(0)
        assert "var(--bg)" in body_rule and "var(--text-1)" in body_rule
        title_rule = re.search(r"\.story-title \{[^}]*\}", html).group(0)
        assert "var(--font-serif)" in title_rule
        meta_rule = re.search(r"\.meta \{[^}]*\}", html).group(0)
        assert "var(--ink-3)" in meta_rule
        # the old hardcoded palette is gone
        for old_hex in ("#f6f7f9", "#1a2233", "#eef0ff", "#4338ca"):
            assert old_hex not in html, f"stale raw hex {old_hex}"

    def test_theme_toggle_button_and_js(self, tmp_path):
        html = _html(tmp_path)
        assert 'id="theme-toggle"' in html
        assert 'aria-label="Đổi giao diện sáng/tối"' in html
        assert "localStorage" in html and "digest-theme" in html
        assert "data-theme" in html

    def test_offline_first_no_external_assets(self, tmp_path):
        html = _html(tmp_path)
        assert "fonts.googleapis.com" not in html
        assert "cdn." not in html
        assert "http" not in html.split("<body", 1)[0].replace(
            "http://www.w3.org", ""
        )  # only the SVG xmlns remains

    def test_font_stacks_are_system_offline(self, tmp_path):
        html = _html(tmp_path)
        assert "Cambria" in html and '"Times New Roman"' in html  # Vietnamese glyphs
        assert "Segoe UI Variable Text" in html
        assert "fonts.googleapis.com" not in html
