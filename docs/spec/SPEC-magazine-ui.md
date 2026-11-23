# Spec: Magazine UI — V1

**Status:** proposed  
**Date:** 2026-11-23  
**Intent:** `docs/intent/magazine-ui.md`  
**Research:** `docs/magazine-ui-research.md`

## Assumptions

1. Đây là một capability duy nhất: **cách trình bày digest hiện có**, không phải initiative nhiều module.
2. Không đổi pipeline, data model, `digest_data`, feedback, Ask, saved/pinned hay localize.
3. Giữ wordmark “Daily AI Digest”, crimson accent và 3 section colors hiện tại; chỉ đổi cách dùng màu.
4. Giữ 30 item, 6 ảnh thật, 3 section, vi/en/ja, print/A4.
5. Không thêm dependency, framework JS hay build step.
6. Hero “A” chỉ dùng ảnh OG/photo thật; figure arXiv không làm hero cover.
7. Section brief dài theo lượng bài; mọi bài trong section phải được nhắc inline.
8. Content-driven section layouts; không ép 3 section cùng một khuôn.
9. Print vẫn text-only, không ảnh/màu.

> Nếu assumption 3 hoặc 8 sai, cần sửa spec trước khi plan.

## Objective

Thay cách trình bày “image-led + 3 khối màu + module lặp” bằng một trang **editorial review** có hierarchy rõ, đọc được 30 item, vẫn có một hero mạnh khi ảnh đủ tốt.

**User:** người đọc cá nhân, mỗi ngày mở digest để scan 30 item và đọc sâu một vài bài.

**Problem:** trang hiện tại cao 7.094px, có 10 background colors, section brief 528 ký tự trải trên 956px, và 3 typographic cover trông như ảnh bị thiếu. Mắt không có điểm bắt đầu; section nào cũng giống nhau.

**Success:** first viewport có một điểm nhấn rõ; section brief đọc được với refs inline; section có nhịp khác nhau; 30 item vẫn đủ; responsive/print/accessibility không regress.

## Tech Stack

- Python 3.12
- Jinja2 templates
- Vanilla CSS + JS trong `templates/`
- `pywebview` cho popup
- pytest cho test
- Không thêm dependency

## Commands

```powershell
# Test
uv run pytest -o addopts='' -p no:cacheprovider -q

# Build
uv build

# Demo render
uv run daily-digest demo --no-open

# Real local run (network + LLM)
uv run daily-digest run --force --date 2026-11-23 --no-notify
```

Visual QA (không phải dependency của project):
- Playwright screenshot ở 1440/1280/1024/768/320.
- A4 PDF để kiểm tra print.

## Project Structure

```text
templates/
  digest.html.j2              # page skeleton, top fold, sections
  partials/_story.html.j2     # story variants + rail
  newsroom.css.j2             # tokens, layout, responsive, print
daily_digest/
  frontpage.py                # lead/secondary/section partition
  render.py                   # render context
  edition.py                  # sidecar data (không đổi shape)
tests/
  test_front_page.py
  test_news_layout.py
  test_render.py
  test_render_images.py
  test_section_briefs.py
  test_ui_tokens.py
docs/
  intent/magazine-ui.md
  magazine-ui-research.md
  spec/SPEC-magazine-ui.md
```

## Code Style

- Jinja: macro nhỏ, một variant một macro; không nhúng logic business vào template.
- CSS: dùng token `var(--...)`; không hardcode hex mới trong component; section color chỉ qua `--section-color`.
- Không inline style.
- Class đặt theo BEM-ish hiện có: `.story--feature`, `.section-summary`, `.cover-pair`.
- Python: type hints, hàm < 50 dòng, không đổi public API nếu không cần.

Ví dụ Jinja:

```jinja
{% macro story(item, variant="brief") %}
<article class="story story--{{ variant }} story--sec-{{ item.section }}"
         id="story-{{ item.item.id }}" data-uid="{{ item.item.id }}">
  ...
</article>
{% endmacro %}
```

Ví dụ CSS:

```css
.story--feature {
  border-top: 3px solid var(--story-accent, var(--red));
  padding-top: 12px;
}
.story--feature .story-title {
  font-size: clamp(28px, 2.8vw, 32px);
}
```

## Testing Strategy

- **Unit/model:** `frontpage.py` partition, no duplicates, 30 item.
- **Render:** story variants, section layouts, Most Read, refs, images, alt.
- **CSS contract:** type scale, section color only rule/label, no full-width brief, no image clamp for More.
- **Section brief:** inline refs, 800–1,200 chars for large section, all uids mentioned.
- **Accessibility:** heading order, button names, contrast tokens, no color-only.
- **Responsive/print:** manual Playwright + A4 PDF; no browser dependency in pytest.
- **Regression:** 571 tests + new tests; CI Windows.

Coverage: giữ hành vi hiện có; không giảm test. Không dùng screenshot test tự động nếu chưa có dependency.

## Boundaries

### Always

- Chạy test, build, demo trước khi báo xong.
- Giữ 30 item, mỗi item một lần.
- Giữ feedback/Ask/saved/pinned/anchors.
- Giữ `digest_data` đúng `date`, `items`, `pinned`.
- Giữ vi/en/ja và localize.
- Giữ print/A4.
- Dùng token màu/typography hiện có.
- Kiểm tra 320/768/1024/1440.

### Ask first

- Đổi palette section colors hoặc wordmark.
- Đổi số item mặc định.
- Thêm dependency (kể cả Playwright vào project).
- Đổi `media.max_images` hoặc policy ảnh.
- Đổi data model/sidecar.

### Never

- Dùng ảnh AI/placeholder giả.
- Full-bleed figure arXiv.
- Khối màu section lớn.
- Brief full-width 956px.
- Giảm item hoặc ẩn summary để trang ngắn.
- Đổi feedback/Ask/saved ngoài phạm vi.
- Commit secret hoặc sửa vendor.

## Requirements

### R1. Page grid

- 12 cột, max-width **1.180px**, gutter **24px**, outer margin **32px**.
- Breakpoints: **1100 / 920 / 760 / 520**.
- Content measure cho brief/summary: **45–75ch**.

### R2. Top fold

- Grid desktop: **7 cột hero + 5 cột Most Read**.
- Hero:
  - Headline **48–56px** serif.
  - Deck/why **18–20px**.
  - Meta **12px** sans.
  - Nếu có `ImageAsset.kind == "og"` và landscape: ảnh **16:9**, `object-fit: cover`, không border.
  - Nếu không có ảnh mạnh: **typographic plate** ink/paper, section label, headline; không dùng section color làm background.
- Most Read: **5 link**, số thứ tự, không ảnh, không feedback/Ask.
- Không render rail trống; source line đặt dưới top fold hoặc trong footer.

### R3. Section head

- Số section + tên + count.
- Section color chỉ dùng cho:
  - rule **2px** dưới head,
  - số section,
  - label 10px.
- Không background màu cho section.
- Heading hierarchy: H2 section, H3 story.

### R4. Section brief

- Vị trí: dưới section head, trước section body.
- Độ dài:
  - **≥10 item:** 800–1.200 ký tự, 2–3 đoạn.
  - **5–9 item:** 500–800 ký tự.
  - **<5 item:** 300–500 ký tự.
- Measure **45–75ch**, đặt trong **5–6 cột**, không full-width.
- **Refs inline tại chỗ nhắc bài**; không tách “refs line”.
- Mọi item trong section phải được nhắc trong brief; có thể gộp nhóm: “Ba bài về X: [a], [b], [c]”.
- Không dùng drop cap.
- Nếu LLM fail: mechanical brief vẫn phải nhắc đủ uid, dùng title + section.

### R5. Section layouts (content-driven)

**Research (nhiều paper):**
- Lead: 7 cột text + 5 cột figure plate (4:3) hoặc không ảnh.
- Briefs: 2 cột, 4–6 brief.
- More: 3 cột, 10–12 item.

**Tech News (ít bài, có OG):**
- 2 feature card (6 cột mỗi card) + list bài còn lại.
- Feature card dùng ảnh OG 16:9 nếu có; nếu không, text + rule.
- Không lặp layout Research.

**Tools & Releases (3–5 bài):**
- Index 3 cột: title, source, summary ngắn.
- Không feature card lớn; brief 300–500 ký tự.

### R6. Images

- **OG/photo:** 16:9, `object-fit: cover`; chỉ hero/feature; caption 11px.
- **Paper figure:** 4:3, `object-fit: contain`, nền `#F3F1EB`, padding 8–12px, border 1px, caption “Figure: arXiv:…”, max-height **280px**.
- **No image:** text + rule; không block màu; typographic plate chỉ cho hero fallback.
- `media.max_images` giữ **6**; không đổi pipeline.
- Ảnh phải có `alt`, `width`, `height`.
- Không dùng logo/brand graphic làm hero.

### R7. Color

- Light: paper `#FBFAF7`, ink `#1A1A1A`, accent `#9F224E`.
- Dark: paper `#121212`, ink `#F2EFE9`, accent `#FF6B6B`.
- Section: `#0F766E`, `#B45309`, `#047857`; dark pastel `#5EEAD4`, `#FCD34D`, `#6EE7B7`.
- Tối đa **một khối màu lớn** trên toàn page.
- Không dùng màu làm tín hiệu duy nhất.

### R8. Typography

- Serif: Newsreader, fallback Cambria/Georgia.
- Sans: Segoe UI/system.
- Scale: **56 / 40 / 28 / 22 / 17 / 15 / 12**.
- Mỗi module tối đa **3 size**.
- Body line-height 1.55–1.65.
- Meta uppercase chỉ cho label.

### R9. Responsive

- **≥1100:** 12 cột; hero 7/5; Research 2 cột; Tech 2 feature; Tools 3 cột.
- **920–1099:** 8 cột; hero stack; section 2 cột; More 2 cột.
- **760–919:** 1 cột; brief 1 cột; More 1 cột.
- **<760:** 1 cột; ảnh full width; feature pair stack; body ≥16px.
- **320:** không multi-column; không color block; không overflow.
- Không horizontal scroll ở 320/768/1024/1440.

### R10. Print/A4

- 2 cột.
- Ẩn ảnh, refs, actions, Ask.
- Hero headline 18pt; section 12pt; story 9.5pt; summary 8.5pt; brief 8.5pt.
- Section color chỉ rule đen; không background.
- Mục tiêu **≤6 trang A4** cho 30 item.

### R11. Accessibility

- Contrast body ≥ **4.5:1**, large ≥ **3:1**.
- 1 H1, H2 section, H3 story; không skip level.
- Button/link có accessible name.
- Focus visible; details/summary keyboard được.
- Ảnh alt + dimensions.
- Không dùng màu đơn thuần để phân biệt section/trạng thái.

### R12. Preserve existing behavior

- 30 item, một occurrence/item.
- Feedback like/dislike/save: 3 button/item.
- Ask input/button/answer mỗi item.
- Saved/pinned; overview anchors; localize; old snapshots.
- `digest_data` shape không đổi.
- Backfill/history counts/dateline không đổi.

## Success Criteria

- [ ] Ở 1280, first viewport có **một** điểm nhấn chính (hero) và **một** module phụ (Most Read); không quá một khối màu lớn.
- [ ] Hero chỉ dùng OG/photo landscape; figure arXiv không full-bleed.
- [ ] Section brief nằm trong 5–6 cột, measure 45–75ch, refs inline, mọi item trong section được nhắc.
- [ ] Research/Tech/Tools có layout khác nhau đúng R5.
- [ ] 3 section colors chỉ xuất hiện ở rule/số/label; không background.
- [ ] 30 item vẫn đủ; mỗi item một lần; 3 feedback + Ask mỗi item.
- [ ] Ảnh OG 16:9; figure 4:3; không ảnh giả.
- [ ] 320/768/1024/1440 không tràn ngang; 320 không multi-column.
- [ ] Dark mode contrast đạt; print ≤6 trang A4.
- [ ] 571 test hiện có + test mới xanh; `uv build`; demo exit 0; CI xanh.

## Out of Scope (Deferred)

- **Image generation / AI placeholder ảnh** — cần provider/chi phí và không phải ảnh bài báo.
- **Tăng số ảnh >6** — cần đo lại dung lượng/tốc độ; để V2.
- **Đổi backend/pipeline/data model** — UI-only.
- **Pagination hoặc giảm số item** — giữ 30.
- **Thay wordmark/palette section** — giữ hiện tại; nếu muốn đổi, spec delta.
- **Browser test dependency** — không thêm Playwright vào project; QA ngoài.
- **Animation/phức tạp JS** — không cần cho V1.

## Implementation notes (2026-11-23)

- `SectionBrief.segments` is additive; sidecars round-trip it, and old snapshots
  fall back to `text` + refs line.
- Briefs below the section minimum trigger one expansion call. Mechanical
  fallback still guarantees every uid when the writer fails.
- A paper figure on the hero is rendered as a labelled 4:3 plate below the
  typographic head. It is not a cover; only OG/photo landscape gets `story--cover`.
- The secondary feature sits below the top fold in a 7/5 text + figure split.
- Print keeps full More summaries, drops images/refs/actions, uses 9.2pt body,
  and fits 30 items in 6 A4 pages on the 2026-11-23 run.

## Open Questions

Không có câu hỏi blocking. Các lựa chọn còn lại đã được chốt bằng assumption 3/8; nếu muốn đổi palette/wordmark, đó là delta spec riêng.

## Approval

Spec này cần được duyệt trước khi viết plan/tasks.  
**Approve / request changes?**
