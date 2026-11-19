"""UI redesign ("Editorial Dark Reading Room") — template assertions per docs/ui-redesign-plan.md.

Step 1: token layer + dark default + light override + theme toggle.
(Later steps append their own test classes here.)"""

import re

from daily_digest.model import RankedItem
from daily_digest.render import render_digest
from helpers import make_config, make_item


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


class TestStep2TypographyHeader:
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
        title_rule = re.search(r"\.card a\.title \{[^}]*\}", html).group(0)
        assert "var(--font-serif)" in title_rule

    def test_sticky_blurred_header(self, tmp_path):
        html = _html(tmp_path)
        header_rule = re.search(r"header \{[^}]*\}", html).group(0)
        assert "position: sticky" in header_rule
        assert "backdrop-filter" in header_rule
        assert "color-mix" in header_rule

    def test_date_uses_mono(self, tmp_path):
        html = _html(tmp_path)
        date_rule = re.search(r"\.date \{[^}]*\}", html).group(0)
        assert "var(--font-mono)" in date_rule

    def test_overview_no_newspaper_drop_cap(self, tmp_path):
        """The drop-cap split Vietnamese words ('H | ôm') — it must stay removed."""
        html = _html(tmp_path)
        assert ".overview p::first-letter" not in html  # drop-cap is gone
        assert "::first-letter" not in html

    def test_overview_is_scannable_bullets(self, tmp_path):
        html = _html(tmp_path)
        assert ".overview-points" in html
        assert 'class="overview-point' in html
        tpl = self._template()
        assert 'overview.split(". ")[:4]' in tpl  # one bullet per sentence, capped
        assert "spotlight" in tpl  # last (takeaway) bullet highlighted

    def test_overview_ai_briefing_surface(self, tmp_path):
        html = _html(tmp_path)
        overview_rule = re.search(r"\.overview \{[^}]*\}", html).group(0)
        assert "linear-gradient" in overview_rule  # gradient surface, not a flat column
        assert ".overview::before" in html and "shimmer" in html  # alive, not static
        assert (
            "animation: none"
            in html.split("prefers-reduced-motion: reduce", 1)[1][:160]
        )
        assert 'id="i-spark"' in html

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


class TestStep3CardsSections:
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
        assert ".idx" in tpl
        assert '"%02d" | format(loop.index)' in tpl

    def test_cards_have_left_bar_and_hover_lift(self, tmp_path):
        html = _html(tmp_path)
        card_rule = re.search(r"\.card \{[^}]*\}", html).group(0)
        assert "border-left: 3px solid" in card_rule
        assert "--section-color" in card_rule
        hover = re.search(r"\.card:hover \{[^}]*\}", html).group(0)
        assert "translateY(-2px)" in hover
        assert "var(--shadow-2)" in hover

    def test_stagger_reveal_with_reduced_motion_guard(self, tmp_path):
        html = _html(tmp_path)
        assert "@keyframes rise" in html
        assert "calc(min(var(--i, 0), 4) * 30ms)" in html  # capped stagger
        assert "prefers-reduced-motion: reduce" in html
        reduced = html.split("prefers-reduced-motion: reduce", 1)[1][:120]
        assert "animation: none" in reduced
        # never fully invisible: fast scrollers/captures must always see content
        rise = html.split("@keyframes rise", 1)[1].split("}", 1)[0]
        assert "opacity: 0.55" in rise and "opacity: 0;" not in rise

    def test_cards_carry_stagger_index_style(self, tmp_path):
        tpl = self._template()
        assert 'style="--i: {{ loop.index0 }}"' in tpl

    def test_meta_is_chips(self, tmp_path):
        tpl = self._template()
        assert '<span class="chip">{{ r.item.points }} points</span>' in tpl
        assert '<span class="chip">{{ r.item.citations }} citations</span>' in tpl

    def test_pinned_section_keeps_test_locked_class(self, tmp_path):
        tpl = self._template()
        assert 'class="block pinned-block"' in tpl  # locked by test_feedback


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
        tpl = self._template()
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

    def test_feedback_states_are_high_contrast(self, tmp_path):
        html = _html(tmp_path)
        done_rule = re.search(r"\.act\.done \{[^}]*\}", html).group(0)
        assert "background: var(--accent)" in done_rule  # solid fill, not outline-only
        assert "color: #ffffff" in done_rule
        failed_rule = re.search(r"\.act\.failed \{[^}]*\}", html).group(0)
        assert "var(--danger)" in failed_rule

    def test_ask_row_is_inline(self, tmp_path):
        html = _html(tmp_path)
        assert "body.bridged .ask { display: flex" in html
        input_rule = re.search(r"\.ask-input \{[^}]*\}", html).group(0)
        assert "flex: 1 1 55%" in input_rule  # input + button share one row

    def test_theme_toggle_icon_swaps_by_theme(self, tmp_path):
        html = _html(tmp_path)
        assert 'class="icon icon-moon"' in html and 'class="icon icon-sun"' in html
        assert '[data-theme="light"] .icon-sun { display: inline; }' in html
        assert '[data-theme="light"] .icon-moon { display: none; }' in html

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
            ("#E8EDF6", "#0B1220", "text-1 on bg"),
            ("#ABB6C9", "#0E1526", "text-2 on card"),
            ("#74829B", "#0B1220", "text-3 on bg"),
            ("#A78BFA", "#0B1220", "why-line on bg"),
            ("#22D3EE", "#0B1220", "link on bg"),
            ("#2DD4BF", "#0B1220", "papers badge on bg"),
            ("#FBBF24", "#0B1220", "news badge on bg"),
            ("#34D399", "#0B1220", "tools badge on bg"),
            ("#F87171", "#0B1220", "danger on bg"),
        ]
        for fg, bg, label in pairs:
            ratio = self._contrast(fg, bg)
            assert ratio >= 4.5, f"dark: {label} = {ratio:.2f}:1 (< 4.5)"

    def test_light_theme_contrast_audit(self):
        pairs = [
            ("#1B2437", "#F6F7FB", "text-1 on bg"),
            ("#46536B", "#FFFFFF", "text-2 on card"),
            ("#5D6878", "#F6F7FB", "text-3 on bg"),
            ("#6D28D9", "#F6F7FB", "why-line on bg"),
            ("#0E7490", "#F6F7FB", "link on bg"),
            ("#0F766E", "#F6F7FB", "papers badge on bg"),
            ("#B45309", "#F6F7FB", "news badge on bg"),
            ("#047857", "#F6F7FB", "tools badge on bg"),
            ("#DC2626", "#F6F7FB", "danger on bg"),
        ]
        for fg, bg, label in pairs:
            ratio = self._contrast(fg, bg)
            assert ratio >= 4.5, f"light: {label} = {ratio:.2f}:1 (< 4.5)"

    def test_light_tokens_match_audited_values(self):
        tpl = self._template()
        light_block = tpl.split('[data-theme="light"] {', 1)[1].split("}", 1)[0]
        for audited in (
            "--text-3: #5D6878",
            "--link: #0E7490",
            "--section-papers: #0F766E",
            "--section-news: #B45309",
            "--section-tools: #047857",
        ):
            assert audited in light_block, (
                f"light token drifted from the contrast audit: {audited}"
            )


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

    def test_dark_is_default_and_light_overrides_exist(self, tmp_path):
        html = _html(tmp_path)
        root = html.split(":root {", 1)[1].split("}", 1)[0]
        assert "--bg: var(--slate-900);" in root  # dark default
        assert '[data-theme="light"]' in html  # explicit light override
        # system-preference light when the user never chose
        assert "@media (prefers-color-scheme: light)" in html
        assert ':root:not([data-theme="dark"])' in html

    def test_component_styles_use_tokens_not_raw_hex(self, tmp_path):
        html = _html(tmp_path)
        body_rule = re.search(r"body \{[^}]*\}", html).group(0)
        assert "var(--bg)" in body_rule and "var(--text-1)" in body_rule
        card_rule = re.search(r"\.card \{[^}]*\}", html).group(0)
        assert "var(--bg-raised)" in card_rule
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
        assert "Segoe UI Variable Serif" in html  # serif stack exists from day one
        assert "Georgia" in html and "system-ui" in html
