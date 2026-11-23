# Task List: Magazine UI — V1

Plan: `tasks/plan.md`  
Spec: `docs/spec/SPEC-magazine-ui.md`

## Task 1: `SectionBrief.segments` + sidecar + mechanical fallback

**Description:** Thêm representation inline cho section brief. `SectionBrief` giữ `text`/`refs`/`coverage_refs` để tương thích, thêm `segments: tuple[OverviewSegment, ...]` additive. Mechanical fallback tạo segments từ title của **mọi** item trong section. Sidecar cũ load `segments=()` và render fallback text + refs line.

**Acceptance criteria:**
- [ ] `SectionBrief.segments` serialize/load roundtrip.
- [ ] Old snapshot không có `segments` vẫn load/render.
- [ ] `heuristic_section_briefs` tạo segments nhắc đủ mọi uid trong section.
- [ ] Không đổi `digest_data`.

**Verification:**
- [ ] `uv run pytest -o addopts='' -p no:cacheprovider -q tests/test_section_briefs.py tests/test_edition.py`
- [ ] Test old snapshot + coverage.

**Dependencies:** None  
**Files likely touched:** `daily_digest/overview.py`, `daily_digest/edition.py`, `tests/test_section_briefs.py`, `tests/test_edition.py`  
**Estimated scope:** Medium  
**Completed:** `5a75d43` — 566 tests pass

## Task 2: Writer inline briefs + validation + prompt + localize

**Description:** Writer trả `[[n]]` inline trong `text`, nhắc mọi item trong section. Prompt dài theo section (≥10 item: 800–1.200 ký tự; 5–9: 500–800; <5: 300–500). Validate markers → segments, đảm bảo mọi uid trong section có ref; một repair; fallback mechanical nếu fail. Localize regenerate từ localized summaries, không fetch/rank/images.

**Acceptance criteria:**
- [ ] Writer output có marker inline, không refs rời.
- [ ] Validation đủ mọi uid; marker sai/ngoài section bị bỏ.
- [ ] Fail → mechanical fallback cho mọi section.
- [ ] Localize giữ ordered uids, backfilled, counts; section brief localized.
- [ ] vi/en/ja tests.

**Verification:**
- [ ] `uv run pytest -o addopts='' -p no:cacheprovider -q tests/test_section_briefs.py tests/test_localize.py tests/test_writer_v2.py`
- [ ] Fake writer coverage/all-item test.

**Dependencies:** Task 1  
**Files likely touched:** `daily_digest/ranking/llm.py`, `daily_digest/ranking/writer_prompts.py`, `daily_digest/pipeline.py`, `daily_digest/localize.py`, `tests/test_section_briefs.py`  
**Estimated scope:** Large (5 files; do not add more)  
**Completed:** `34f7c46` — 566 tests pass

## Task 3: Render brief inline refs trong cột hẹp

**Description:** Render `SectionBrief.segments` inline dưới section head. Bỏ dòng refs rời cho brief mới; brief nằm trong 5–6 cột, measure 45–75ch, 2–3 đoạn. Old snapshot fallback vẫn render text + refs line.

**Acceptance criteria:**
- [ ] New brief: refs nằm trong câu, không có `.section-summary-refs` rời.
- [ ] Brief width ≤ ~6 cột, không full-width 956px.
- [ ] Old snapshot vẫn có refs line.
- [ ] Mọi uid trong section có anchor.

**Verification:**
- [ ] `uv run pytest -o addopts='' -p no:cacheprovider -q tests/test_section_briefs.py tests/test_ui_tokens.py`
- [ ] Screenshot 1280.

**Dependencies:** Task 1, Task 2  
**Files likely touched:** `templates/digest.html.j2`, `templates/newsroom.css.j2`, `tests/test_section_briefs.py`  
**Estimated scope:** Small/Medium  
**Completed:** `9b7277d` — 567 tests pass

## Checkpoint: Brief system

- [ ] Old snapshot loads/render.
- [ ] 30/30 uid coverage.
- [ ] vi/en/ja fallback.
- [ ] Tests pass.
- [ ] Human review before section layouts.

## Task 4: Grid/type/spacing tokens + section head

**Description:** Token hóa grid 12 cột, max 1.180px, gutter 24px; type scale 56/40/28/22/17/15/12; section head chỉ dùng section color cho rule 2px/số/label. Không background màu.

**Acceptance criteria:**
- [ ] CSS tokens cho grid/type; không hardcode hex mới.
- [ ] Section head không background màu.
- [ ] Module tối đa 3 size.
- [ ] Test token pass.

**Verification:**
- [ ] `uv run pytest -o addopts='' -p no:cacheprovider -q tests/test_ui_tokens.py`
- [ ] Screenshot 1280/760.

**Dependencies:** None  
**Files likely touched:** `templates/newsroom.css.j2`, `tests/test_ui_tokens.py`  
**Estimated scope:** Small  
**Completed:** `39fa813` — 44 UI token tests pass

## Task 5: Top fold hero 7/5 + Most Read 5

**Description:** Top fold chỉ hero 7 cột + Most Read 5 link. Bỏ secondary feature khỏi top fold; item secondary trở về section. Hero OG/photo 16:9; không ảnh mạnh → typographic plate ink/paper. Source line dưới top fold/footer.

**Acceptance criteria:**
- [ ] Top fold có hero + Most Read; không secondary card.
- [ ] Mỗi item vẫn xuất hiện đúng một lần.
- [ ] Most Read 5 link, không feedback/Ask.
- [ ] Hero không dùng section color background.

**Verification:**
- [ ] `uv run pytest -o addopts='' -p no:cacheprovider -q tests/test_front_page.py tests/test_news_layout.py tests/test_cover_hero.py`
- [ ] Screenshot 1280.

**Dependencies:** Task 4  
**Files likely touched:** `daily_digest/frontpage.py`, `templates/digest.html.j2`, `tests/test_front_page.py`, `tests/test_news_layout.py`  
**Estimated scope:** Medium  
**Completed:** `639559d` — 567 tests pass

## Checkpoint: Skeleton

- [ ] First viewport có một điểm nhấn.
- [ ] Không còn rail trống/full-width brief.
- [ ] Tests pass.
- [ ] Human review.

## Task 6: Research layout

**Description:** Research = lead 7/5 (text + figure plate/không ảnh), briefs 2 cột, more 3 cột. Brief dài 800–1.200, refs inline.

**Acceptance criteria:**
- [ ] Research dùng layout riêng, không lặp.
- [ ] Lead + 4–6 brief + more 3 cột.
- [ ] Không ảnh full-bleed cho figure arXiv.
- [ ] 30 item tests pass.

**Verification:**
- [ ] `uv run pytest ... tests/test_news_layout.py tests/test_section_briefs.py`
- [ ] Screenshot 1280/760.

**Dependencies:** Task 3, Task 5  
**Files likely touched:** `templates/digest.html.j2`, `templates/newsroom.css.j2`, `tests/test_news_layout.py`  
**Estimated scope:** Medium  
**Completed:** `6e99939` — layout tests pass

## Task 7: Tech layout

**Description:** Tech = 2 feature card (6 cột mỗi card) + list bài còn lại. Feature dùng OG 16:9 nếu có; không ảnh thì text + rule; không color block.

**Acceptance criteria:**
- [ ] Tech có 2 feature + list.
- [ ] Ảnh OG 16:9, không figure plate.
- [ ] Không lặp Research layout.
- [ ] Mobile stack.

**Verification:**
- [ ] `uv run pytest ... tests/test_news_layout.py tests/test_render_images.py`
- [ ] Screenshot 1280/760.

**Dependencies:** Task 3, Task 5  
**Files likely touched:** `templates/digest.html.j2`, `templates/newsroom.css.j2`, `tests/test_news_layout.py`  
**Estimated scope:** Medium

## Task 8: Tools index 3 cột

**Description:** Tools = index 3 cột: title, source, summary; brief 300–500 ký tự. Không feature card.

**Acceptance criteria:**
- [ ] Tools index 3 cột desktop, 1 cột mobile.
- [ ] Không feature/ảnh lớn.
- [ ] Brief ngắn theo section.
- [ ] Tests pass.

**Verification:**
- [ ] `uv run pytest ... tests/test_news_layout.py tests/test_section_briefs.py`
- [ ] Screenshot 1280/760.

**Dependencies:** Task 3, Task 5  
**Files likely touched:** `templates/digest.html.j2`, `templates/newsroom.css.j2`, `tests/test_news_layout.py`  
**Estimated scope:** Small/Medium

## Checkpoint: Section layouts

- [ ] 3 layout khác nhau đúng spec.
- [ ] 30 item một occurrence.
- [ ] Tests + screenshots.
- [ ] Human review.

## Task 9: Images OG/figure/typographic fallback

**Description:** `_story` hỗ trợ OG 16:9 `cover` cho hero/feature, figure 4:3 `contain` plate cho section, typographic fallback chỉ hero. Không ảnh giả, không full-bleed figure.

**Acceptance criteria:**
- [ ] OG 16:9, figure 4:3 plate.
- [ ] Hero không nhận figure.
- [ ] No-image không tạo block màu.
- [ ] alt/width/height.

**Verification:**
- [ ] `uv run pytest ... tests/test_render_images.py tests/test_cover_hero.py tests/test_media.py`
- [ ] Screenshot 1280.

**Dependencies:** Task 5  
**Files likely touched:** `templates/partials/_story.html.j2`, `templates/newsroom.css.j2`, `tests/test_render_images.py`  
**Estimated scope:** Medium

## Task 10: Responsive 320/768/1024/1440

**Description:** Breakpoints 1100/920/760/520; hero stack, section 2→1 cột, briefs 2→1, more 3→2→1; 320 không multi-column/overflow.

**Acceptance criteria:**
- [ ] No horizontal scroll 320/768/1024/1440.
- [ ] 320 body ≥16px, no color block.
- [ ] Cover pair stack <760.
- [ ] Playwright screenshots.

**Verification:**
- [ ] `uv run pytest ... tests/test_ui_tokens.py tests/test_news_layout.py`
- [ ] Playwright audit.

**Dependencies:** Task 6, 7, 8, 9  
**Files likely touched:** `templates/newsroom.css.j2`, `tests/test_ui_tokens.py`  
**Estimated scope:** Small

## Task 11: Dark + print + contrast

**Description:** Dark tokens; typographic cover contrast; print 2 cột, ẩn ảnh/refs/color, ≤6 A4; body 4.5:1/large 3:1.

**Acceptance criteria:**
- [ ] Dark covers dark text on pastel.
- [ ] Print ≤6 pages, no images/color.
- [ ] Contrast checks.
- [ ] No color-only state.

**Verification:**
- [ ] `uv run pytest ... tests/test_ui_tokens.py tests/test_locale_render.py`
- [ ] Playwright contrast + PDF page count.

**Dependencies:** Task 10  
**Files likely touched:** `templates/newsroom.css.j2`, `tests/test_ui_tokens.py`  
**Estimated scope:** Small/Medium

## Checkpoint: UI complete

- [ ] 320/768/1024/1440 no overflow.
- [ ] Print ≤6 A4.
- [ ] Contrast pass.
- [ ] Human review.

## Task 12: Full QA + docs + CI

**Description:** Chạy full suite/build/demo/real run; screenshots; cập nhật README/CHANGELOG/docs; commit + push; CI xanh.

**Acceptance criteria:**
- [ ] Full suite pass.
- [ ] Build pass.
- [ ] Demo exit 0.
- [ ] Real 30-item run + screenshots.
- [ ] CI success.

**Verification:**
- [ ] `uv run pytest -o addopts='' -p no:cacheprovider -q`
- [ ] `uv build`
- [ ] `uv run daily-digest demo --no-open`
- [ ] `uv run daily-digest run --force --date 2026-11-23 --no-notify`
- [ ] `gh run watch`

**Dependencies:** All  
**Files likely touched:** `README.md`, `CHANGELOG.md`, docs, tests  
**Estimated scope:** Medium
