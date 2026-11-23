# Implementation Plan: Magazine UI — V1

Source spec: `docs/spec/SPEC-magazine-ui.md`  
Intent: `docs/intent/magazine-ui.md`  
Research: `docs/magazine-ui-research.md`

## Overview

Chuyển digest từ image-led + khối màu + module lặp sang **editorial review**: một hero “A” khi có ảnh OG/photo mạnh, brief dài có refs inline, section layout theo nội dung, màu section chỉ làm rule/label. Giữ nguyên 30 item, feedback/Ask/saved, vi/en/ja, print/A4 và `digest_data`.

## Architecture Decisions

1. **Inline refs cần additive `SectionBrief.segments`.**
   Spec giả định “không đổi data model”, nhưng yêu cầu refs inline + mọi bài được nhắc không thể làm chỉ bằng `text` + `refs` rời. Thêm `segments` (giống `OverviewPoint`) là additive; sidecar cũ vẫn load và fallback sang text + refs line. Đây là deviation cần duyệt.

2. **Top fold chỉ hero + Most Read.**
   Bỏ secondary feature khỏi top fold; item secondary trở về section của nó. `FrontPage` vẫn giữ `secondary` nếu cần backward compatibility, nhưng template không render nó ở top fold.

3. **Section layouts content-driven.**
   Research = lead + briefs + more; Tech = 2 feature card + list; Tools = index 3 cột. Không thêm JS/framework; dùng Jinja branch + CSS.

4. **Hai treatment ảnh.**
   OG/photo 16:9 `cover` cho hero/feature; figure arXiv 4:3 plate `contain` cho section. Không đổi `collect_images`/`media.max_images` trong V1.

5. **Brief generation thay đổi ở writer.**
   Writer nhận marker `[[n]]`, phải nhắc mọi item trong section, text dài theo section. Mechanical fallback tạo segments từ title để không mất coverage.

6. **Giữ palette/wordmark.**
   Teal/amber/green chỉ rule/số/label; crimson giữ cho brand/accent.

## Task List

### Phase 1: Brief system (critical path)

- [x] Task 1: `SectionBrief.segments` + sidecar + mechanical fallback (`5a75d43`)
- [x] Task 2: Writer inline briefs + validation + prompt + localize (`34f7c46`)
- [x] Task 3: Render brief inline refs trong cột hẹp (`9b7277d`)

### Checkpoint: Brief system
- [x] Old snapshot vẫn load/render
- [x] 30 uid coverage
- [x] vi/en/ja fallback
- [x] Tests pass

### Phase 2: Page skeleton

- [x] Task 4: Grid/type/spacing tokens + section head (`39fa813`)
- [x] Task 5: Top fold hero 7/5 + Most Read 5; secondary feature below (`639559d`)

### Checkpoint: Skeleton
- [x] 1280 first viewport có một điểm nhấn
- [x] Không còn rail trống/full-width brief
- [x] Tests pass

### Phase 3: Section layouts

- [x] Task 6: Research layout (lead + briefs + more 3 cột) (`6e99939`)
- [x] Task 7: Tech layout (2 feature + list) (`acfa0de`)
- [x] Task 8: Tools index 3 cột (`a15238b`)

### Checkpoint: Section layouts
- [ ] 3 layout khác nhau đúng spec
- [ ] 30 item một occurrence
- [ ] Tests pass + screenshot

### Phase 4: Images, responsive, print

- [x] Task 9: OG/photo 16:9 + figure 4:3 + typographic fallback (`419f97d`)
- [ ] Task 10: Responsive 320/768/1024/1440
- [ ] Task 11: Dark + print/A4 + contrast

### Checkpoint: UI complete
- [ ] 320/768/1024/1440 no overflow
- [ ] Print ≤6 A4 pages
- [ ] Contrast pass

### Phase 5: QA

- [ ] Task 12: Full regression, demo, real run, docs/changelog, CI

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Inline refs require data model change | High | Additive `segments`; old snapshots fallback; spec deviation explicit |
| Brief 800–1.200 chars for 22 items becomes wall of text | High | Constrain measure 45–75ch, 2–3 paragraphs, test readability; fallback if writer misses items |
| Writer fails to mention every item | High | Validation coverage; mechanical fallback; no silent omission |
| Removing secondary feature changes test expectations | Medium | Update front page tests deliberately; verify every item once |
| Image scarcity makes Tech 2-feature fragile | Medium | Feature card works without image; no color block; text-first fallback |
| Page becomes longer | Medium | Accepted by user; check print ≤6 pages; more band 3 cols |
| Print typographic plate/color leaks | Medium | Print overrides: no background/image/refs |
| Old snapshot/localize breaks | High | Sidecar compatibility tests; localize identity tests |

## Open Questions

1. **Approve additive `SectionBrief.segments`?** Cần cho refs inline; nếu không, phải giữ refs line rời (trái intent).
2. **Approve bỏ secondary feature khỏi top fold?** Spec R2 chỉ có hero + Most Read; secondary trở về section.
3. **Approve brief dài 800–1.200 ký tự cho Research?** Bạn đã chọn A; xác nhận page dài hơn là chấp nhận được.

## Approval

Plan này cần được duyệt trước khi implement.  
**Approve / request changes?**
