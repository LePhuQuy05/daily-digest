# Intent: Magazine-style UI for Daily AI Digest

**Confirmed:** 2026-11-23  
**Status:** confirmed by user  
**Source:** interview based on `docs/magazine-ui-research.md`

## Outcome

Digest 30 item theo hướng **editorial review (B)**, với **một hero “A”** khi có ảnh OG/photo thật đủ mạnh; còn lại typography/grid dẫn dắt.

## Users and jobs

- **User:** người đọc cá nhân, đọc 30 item mỗi ngày.
- **Job:** scan nhanh để chọn bài, nhưng vẫn đọc sâu được từng item.
- **Why now:** UI hiện tại quá nhiều khối màu/ảnh giả, section brief full-width khó đọc, và mọi section lặp cùng một nhịp.

## Confirmed decisions

### Hero

- Chỉ **một hero “A”** ở đầu trang.
- Chỉ dùng ảnh **OG/photo thật, landscape**.
- Không dùng logo/chart/brand graphic làm hero.
- Figure arXiv dùng **figure plate 4:3**, nền trung tính, caption; không full-bleed.
- Không có ảnh mạnh → **typographic plate tối giản** (ink/paper), không dùng khối màu section.

### Section brief

- **800–1.200 ký tự** cho section lớn; section ít bài thì ngắn hơn theo lượng bài.
- **2–3 đoạn**.
- **Refs inline ngay chỗ nhắc bài**, không tách thành một dòng refs riêng.
- Mọi bài trong section phải được nhắc trong brief; không bỏ bài nào.

### Color

- Giữ **3 màu section**.
- Chỉ dùng cho **rule 2px**, **số section**, **label 10px**.
- Không dùng background màu lớn cho section.
- Tối đa **một khối màu lớn** trên toàn trang (hero fallback nếu cần).

### Layout

Content-driven, không lặp cùng một layout cho cả 3 section:

- **Research:** lead + briefs.
- **Tech News:** 2 feature card + list.
- **Tools & Releases:** index 3 cột gọn.

Top fold:

- Hero + **Most Read 5 link**.

## Success criteria

- First viewport có **một điểm nhấn rõ** (hero), không tranh chấp với nhiều khối lớn.
- Section brief đọc được: measure **45–75ch**, refs inline, không full-width 956px.
- Đủ **30 item**, mỗi item xuất hiện đúng một lần.
- Ảnh OG **16:9**, figure paper **4:3**; không trộn treatment.
- 320 / 768 / 1024 / 1440 không tràn ngang; 320 không multi-column.
- Contrast body **≥4.5:1**, large text **≥3:1**.
- Print **≤6 trang A4**, không ảnh/màu.
- Toàn bộ test hiện có + test layout mới xanh; CI xanh.

## Constraints

- Chỉ có **6/30 ảnh thật**; không dùng ảnh giả/AI-generated.
- Giữ **30 item**.
- Giữ **vi/en/ja**.
- Giữ feedback, Ask, saved/pinned, overview anchors.
- Giữ print/A4.
- Không thêm dependency mới.
- Không đổi data model/feedback/Ask.

## Out of scope

- Không làm **image-led toàn trang**.
- Không dùng ảnh AI/placeholder giả.
- Không giảm số item xuống dưới 30.
- Không đổi `digest_data` shape, feedback, Ask, saved/pinned.
- Không thiết kế lại backend/pipeline trong phạm vi này.

## Open decisions (for the spec/plan)

1. Có giữ đúng 3 section color hiện tại (teal/amber/green) hay đổi palette?
2. Có giữ wordmark “Daily AI Digest” và crimson accent hiện tại không?
3. Có cần một “cover story” full-width khác ngoài hero không, hay hero là cover duy nhất?

## Next

1. Viết spec UI từ intent này (`spec-driven-development`).
2. Chia task theo phase.
3. Implement + QA theo spec.
