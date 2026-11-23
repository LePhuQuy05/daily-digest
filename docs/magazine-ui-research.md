# Nghiên cứu UI magazine cho Daily AI Digest

**Ngày:** 2026-11-23  
**Phạm vi:** cách trình bày trang digest 30 item, 6 ảnh thật, 3 section, có print/A4 và 3 locale.  
**Mục tiêu:** đủ cụ thể để bạn lên plan, không phải một danh sách “làm đẹp hơn”.

---

## 0. Kết luận ngắn

UI hiện tại có nguyên liệu tốt — typography serif, section rõ, ảnh thật, refs đầy đủ — nhưng **hierarchy đang sai**. Trang đang cố làm magazine bằng cách:

- phóng to ảnh và headline,
- thêm 3 khối màu section bão hòa,
- lặp lại cùng một nhịp “feature → brief → more” ở mọi section.

Kết quả là mắt không biết nhìn đâu trước, các khối màu trông như placeholder, và trang dài 7.094px ở 1280px.

**Đề xuất:** chuyển từ **image-led magazine** sang **editorial review** — vẫn có ảnh lớn ở đúng chỗ, nhưng màu chỉ dùng làm tín hiệu section, typography và khoảng trắng làm hierarchy. Đây là hướng hợp với dữ liệu thật: 24/30 bài không có ảnh dùng được, phần lớn ảnh còn lại là figure arXiv chứ không phải ảnh editorial.

---

## 1. Audit UI hiện tại

### 1.1 Số đo thực tế

Đo trên `output/digest-2026-11-23.html` (Playwright, 1280×900):

| Chỉ số | Giá trị | Nhận xét |
|---|---:|---|
| Chiều cao trang | **7.094px** | ~7,9 viewport; rất dài, thiếu nhịp nghỉ |
| Content width | **1.040px** | Ổn cho desktop |
| Hero headline | **58px** | Đủ mạnh |
| Section title | **22px** | Hơi nhỏ so với hero |
| Brief title | **17px** | Ổn |
| Body summary | **14.5px** | Hơi nhỏ cho đoạn dài |
| Section brief width | **956px** | Quá rộng để đọc |
| Section brief dài | **528 / 505 / 438 ký tự** | Là article paragraph, không phải deck |
| Background colors | **10** | Quá nhiều tín hiệu màu |
| Ảnh thật | **6 / 30** | 80% bài không có ảnh |
| Typographic covers | **3** | Đang là khối màu lớn |
| Feature cards | **2** + 3 section lead + hero | 6 feature module |

### 1.2 Bảy vấn đề cụ thể

1. **Quá nhiều điểm tranh chấp thị giác.** Hero ảnh lớn, 2 feature card, 3 section lead, 3 khối màu, red accent và 6 ảnh cùng lúc. Squint test không cho một điểm bắt đầu rõ ràng.
2. **Màu đang làm decoration, không làm hierarchy.** Teal, amber, green, crimson + paper/ink = 10 background colors. Khi section nào cũng có một khối màu lớn, màu không còn phân biệt section nữa; nó chỉ làm trang nặng.
3. **Section brief quá rộng và quá dài.** 528 ký tự trên 956px tạo line length ~130 ký tự, vượt xa ngưỡng đọc thoải mái 45–90 ký tự. Đây là lỗi readability, không phải lỗi thẩm mỹ.
4. **Typographic cover trông giống ảnh bị thiếu.** Một khối màu lớn có chữ trắng đọc như placeholder. Khi đặt cạnh ảnh thật, nó làm người đọc nghĩ “bài này không có ảnh” thay vì “đây là chủ ý thiết kế”.
5. **Nhịp lặp lại.** Section nào cũng lead + 6 brief + more band; không có section nào “nhẹ” hơn để tạo pacing. Magazine thật thay đổi nhịp: có spread lớn, có cột chữ, có index nhỏ.
6. **Ảnh không đồng nhất.** Ảnh OG (16:9), figure arXiv (4:3, nền trắng), logo/brand graphic bị reject — mỗi loại cần một treatment khác. Hiện tại tất cả cùng nằm trong một khung, cùng border/padding, nên figure paper trông như ảnh editorial.
7. **Trang quá dài mà không có “landmark”.** 7.094px nhưng không có mốc nào đủ mạnh để người đọc nhớ “đang ở section nào”. Section head 22px không đủ làm landmark.

### 1.3 Điểm đang tốt (giữ lại)

- Typography serif có cá tính; không bị “AI aesthetic” kiểu tím/gradient/rounded card.
- Section structure rõ: Research / Tech News / Tools & Releases.
- 30 item vẫn đủ, refs phủ 30/30.
- Ảnh thật, alt text, width/height đầy đủ.
- 320/768/1024/1440 không tràn ngang; console không lỗi.
- Dark mode contrast đã đạt; print text-only 6 trang A4.
- Nền tảng kỹ thuật tốt: token, test 574, CI xanh.

---

## 2. Nghiên cứu: magazine/editorial làm hierarchy bằng gì?

### 2.1 Nguồn chính

| Nguồn | Điều đáng học | Điều không nên copy |
|---|---|---|
| **Nielsen Norman Group — Visual Hierarchy in UX** (2021) | Hierarchy đến từ contrast, scale, grouping/whitespace. Khuyến nghị **tối đa 2 primary + 2 secondary colors**, **tối đa 3 size** trong một module, và dùng **squint test**. | Không phải mọi trang cần 3 size; đây là hướng dẫn web UX, không phải magazine art direction. |
| **WIRED — Welcome to the New WIRED** (2015) | Card motif để scannable, responsive, typography riêng, giảm clutter, tăng tốc tải. | Card grid đồng nhất không tạo ra magazine; WIRED có ảnh và art direction rất mạnh. |
| **The Atlantic — website redesign** (2015) | Full-bleed images, module linh hoạt, “Most Popular”, navigation đơn giản, mobile-first. | Full-bleed chỉ đẹp khi ảnh đủ mạnh; 6/30 ảnh và figure paper không phù hợp full-bleed. |
| **NYT — redesign** (2014/2018) | Reading experience immersive, ảnh lớn, story scroll, section rõ. | Cần hệ thống ảnh/illustration và editorial resources rất lớn. |
| **Butterick’s Practical Typography — Line length** | Line length trung bình **45–90 ký tự**; web.dev nhắc 66 ký tự là lý tưởng. | Không áp dụng nguyên cho mobile; mobile cần 1 cột và measure hẹp hơn. |
| **W3C WCAG 2.2 — Contrast (Minimum)** | Body text **4.5:1**, large text **3:1**. | Không đủ để tạo hierarchy; contrast chỉ là điều kiện đọc. |

### 2.2 Bài học cho Daily AI Digest

1. **Magazine không phải là nhiều ảnh + nhiều màu.** Magazine là **nhịp**: một điểm nhấn lớn, vài module vừa, phần còn lại là index/typography.
2. **Với 6/30 ảnh, không thể lấy ảnh làm hệ thống chính.** Ảnh phải là “feature”, không phải background cho mọi section.
3. **Màu section chỉ nên là tín hiệu nhỏ.** Một rule 2px, một label 10px, một số thứ tự — đủ để phân biệt mà không phá hierarchy.
4. **Section brief là deck, không phải bài viết.** 2–3 câu, measure 45–75 ký tự, không phải 528 ký tự full-width.
5. **Typographic cover chỉ dùng cho 1–2 vị trí đặc biệt.** Nếu dùng cho 3 feature, nó thành pattern và mất tính “đặc biệt”.
6. **Ảnh paper khác ảnh editorial.** Figure arXiv cần “figure plate” (nền trung tính, caption, tỉ lệ 4:3), không phải crop 16:9 như ảnh OG.

---

## 3. Ba hướng trình bày

### A. Editorial review (khuyến nghị)

Typography dẫn dắt, ảnh là điểm nhấn có chọn lọc, màu section chỉ là rule/label.

- **Ưu:** hợp với 24/30 bài không ảnh; đọc tốt; print đẹp; ít rủi ro hình ảnh; lên plan rõ.
- **Nhược:** ít “wow” hơn image-led; cần đầu tư type scale và spacing.
- **Dành cho:** người đọc thật, đọc 30 bài, không chỉ lướt ảnh.

### B. Image-led magazine (hướng hiện tại)

Ảnh lớn, khối màu, feature card.

- **Ưu:** ấn tượng mạnh nếu ảnh đẹp và đồng nhất.
- **Nhược:** 6/30 ảnh, figure paper, logo/brand graphic bị reject → nhiều “lỗ hổng” phải lấp bằng khối màu; dễ thành placeholder.
- **Dành cho:** khi có 15–20 ảnh editorial chất lượng, hoặc có art direction/ảnh minh họa riêng.

### C. Print review / data-dense

Grid 2–3 cột, ảnh nhỏ, nhiều rule, kiểu Monocle/Aeon.

- **Ưu:** chứa 30 item rất gọn; scannable; print tốt.
- **Nhược:** dễ quay lại cảm giác “broadsheet” mà bạn vừa chê; ít cảm xúc.
- **Dành cho:** người đọc muốn scan nhanh, không cần cover story.

**Khuyến nghị: A + một chút B.** Một hero/feature có ảnh mạnh, 1–2 feature phụ, còn lại editorial typography. Không dùng full color block cho section.

---

## 4. Cách trình bày đề xuất

### 4.1 Skeleton desktop (≥1100px)

```
┌──────────────────────────────────────────────────────────────┐
│ MASTHEAD: wordmark | date/issue | language/theme/saved       │
├──────────────────────────────────────────────────────────────┤
│ NAV: Research · Tech News · Tools · Saved                    │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌───────────────────────────────┐  ┌─────────────────────┐  │
│  │ LEAD STORY                    │  │ MOST READ            │  │
│  │ kicker / 48–56px headline     │  │ 01  …                │  │
│  │ deck 20px / 2 lines           │  │ 02  …                │  │
│  │ meta 12px                     │  │ 03  …                │  │
│  │ [ ảnh 16:9 nếu là OG/photo ]  │  │ 04  …                │  │
│  │ [ figure plate nếu arXiv ]    │  │ 05  …                │  │
│  └───────────────────────────────┘  └─────────────────────┘  │
│                                                              │
│  ┌──────────────────────┐  ┌──────────────────────┐          │
│  │ FEATURE 2            │  │ FEATURE 3            │          │
│  │ headline 28–32px     │  │ headline 28–32px     │          │
│  │ 1–2 câu              │  │ 1–2 câu              │          │
│  │ ảnh nhỏ hoặc không   │  │ ảnh nhỏ hoặc không   │          │
│  └──────────────────────┘  └──────────────────────┘          │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│ 01 RESEARCH                                    12 stories    │
│ ── section rule 2px, màu section, không background           │
│                                                              │
│  ┌───────────────────────────────┐  ┌─────────────────────┐  │
│  │ section lead                  │  │ section brief       │  │
│  │ headline 28px                 │  │ 2–3 câu, 45–75ch    │  │
│  │ deck / why                    │  │ 3 inline refs       │  │
│  │ figure/ảnh 4:3 hoặc 16:9      │  │ “Còn lại” chips     │  │
│  └───────────────────────────────┘  └─────────────────────┘  │
│                                                              │
│  ┌──────────────────────┐  ┌──────────────────────┐          │
│  │ brief 01             │  │ brief 02             │          │
│  │ 17px headline        │  │ 17px headline        │          │
│  │ summary 3–4 dòng     │  │ summary 3–4 dòng     │          │
│  │ thumb 96px (nếu có)  │  │ thumb 96px (nếu có)  │          │
│  └──────────────────────┘  └──────────────────────┘          │
│  … 4 brief nữa, 2 cột                                        │
│                                                              │
│  MORE IN THIS SECTION — 3 cột, 10–12 item, summary đầy đủ   │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 Grid và spacing

- 12 cột, max-width **1.180px**, gutter **24px**, outer margin **32px**.
- Baseline spacing scale: **8px**. Dùng 8/16/24/32/48/64.
- Section gap: **56–64px**; module gap: **24px**; paragraph gap: **10–12px**.
- Section brief không full-width: đặt trong **5–6 cột**, measure **45–75ch**.

### 4.3 Typography

Giữ font hiện có (Newsreader + Segoe UI), không thêm dependency.

| Vai trò | Size | Weight | Font |
|---|---:|---:|---|
| Wordmark | 32–40px | 700 | serif |
| Hero headline | 48–56px | 700 | serif |
| Feature headline | 28–32px | 700 | serif |
| Section title | 24–28px | 700 | serif |
| Story title | 17–20px | 700 | serif |
| Deck / why | 16–18px | 400 | serif |
| Summary | 14–15px | 400 | serif |
| Meta / label | 11–12px | 600 | sans |
| Section number | 18–22px | 700 | serif |

Quy tắc:

- Mỗi module tối đa **3 size**.
- Không dùng quá **5 size** trên toàn trang (hiện tại hero 58, section 22, brief 17, summary 14.5, meta 10.5 = 5, nhưng thiếu 28/32 cho feature).
- Body/summary line-height 1.55–1.65.
- Meta uppercase chỉ dùng cho label, không dùng cho đoạn dài.

### 4.4 Màu

**Light**

- Paper: `#FBFAF7`
- Ink: `#1A1A1A`
- Accent: `#9F224E` (chỉ link/active/brand)
- Section colors: teal `#0F766E`, amber `#B45309`, green `#047857` — **chỉ dùng cho rule 2px, số section, label 10px**.

**Dark**

- Paper: `#121212`
- Ink: `#F2EFE9`
- Accent: `#FF6B6B`
- Section colors: pastel `#5EEAD4`, `#FCD34D`, `#6EE7B7` — chỉ rule/label, không background.

Quy tắc:

- Tối đa **1 khối màu lớn** trên toàn page (hero cover nếu không có ảnh).
- Section không dùng background màu; dùng border-left 2px + label.
- Typographic cover chỉ dùng cho **1 feature** khi không có ảnh, nền ink/paper, không dùng 3 màu section.
- Không dùng màu làm tín hiệu duy nhất; luôn có số/label.

### 4.5 Hệ thống ảnh

Hai treatment, không trộn:

**A. Editorial image (OG/photo)**

- Tỉ lệ **16:9**, `object-fit: cover`, không border, caption 11px.
- Chỉ dùng cho hero/feature khi ảnh là ảnh thật, không phải logo/chart.
- Không full-bleed nếu ảnh < 800px.

**B. Paper figure**

- Tỉ lệ **4:3**, `object-fit: contain`, nền `#F3F1EB`, padding 8–12px, border 1px.
- Caption `Figure: arXiv:...`; max-height **240–280px**.
- Không crop, không dùng làm cover.

**Không có ảnh**

- Không tạo khối màu lớn.
- Feature không ảnh dùng **typographic plate**: nền ink/paper, số section, title; chỉ 1 lần.
- Brief không ảnh dùng text + rule, không placeholder.

### 4.6 Section brief và refs

- Brief **2–3 câu**, **280–320 ký tự** (không phải 600).
- Measure **45–75ch**, đặt trong 5–6 cột, không full-width.
- 3 inline refs ở cuối brief; coverage refs hiển thị thành **chip line** nhỏ, có thể wrap 2 dòng, không phải paragraph.
- Label “CÒN LẠI N BÀI” 10px uppercase; refs 11–12px.
- Không dùng drop cap; người Việt dễ bị tách chữ.

### 4.7 Nhịp 30 item

- **1 hero** + **2 feature** + **3 section lead** = 6 điểm nhấn.
- Mỗi section: lead + **4–6 brief** + more band.
- More band: **3 cột** ở desktop, summary đầy đủ nhưng font 13.5px; 2 cột ở 920px; 1 cột ở 760px.
- Xen kẽ section có ảnh và section typographic để tạo nhịp; không section nào giống hệt section nào.
- More band có thể là “index” nhỏ, không cần ảnh; đây là nơi đọc nhanh.

### 4.8 Responsive

| Width | Layout |
|---|---|
| ≥1100 | 12 cột; hero 7/5; section lead 7/5; briefs 2 cột; more 3 cột |
| 768–1099 | 8 cột; hero stack; section 2 cột; briefs 2 cột; more 2 cột |
| <768 | 1 cột; hero ảnh full width; feature pair stack; briefs 1 cột; more 1 cột |
| 320 | Không multi-column; body ≥16px; image full width; không color block |

Kiểm tra: 320/768/1024/1440, không horizontal scroll, không console error.

### 4.9 Print/A4

- 2 cột, không ảnh, không background màu.
- Hero 18pt, section title 12pt, story 9.5pt, summary 8.5pt.
- Section brief 8.5pt, refs ẩn.
- Mục tiêu **≤6 trang A4** cho 30 item (hiện 6 trang).

### 4.10 Accessibility

- Body 4.5:1, large 3:1 (W3C).
- Ảnh alt + width/height.
- Button/link accessible name.
- Heading: 1 H1, H2 section, H3 story.
- Focus visible; `details/summary` keyboard được.
- Không dùng màu làm tín hiệu duy nhất.

---

## 5. Tiêu chí nghiệm thu đề xuất

- [ ] Ở 1280, first viewport có **một** điểm nhấn chính (hero) và **một** điểm phụ (Most Read); không quá 1 khối màu lớn.
- [ ] Section brief ≤ **320 ký tự**, measure **45–75ch**, không full-width.
- [ ] Tối đa **3 size** trong một module; toàn trang không quá 5 size.
- [ ] Tối đa **2 primary + 2 secondary** màu; section color chỉ rule/label.
- [ ] 6 ảnh thật: ảnh OG 16:9, figure paper 4:3; không trộn treatment.
- [ ] 30 item vẫn đủ; mỗi item một lần; refs phủ 30/30.
- [ ] 320/768/1024/1440 không tràn ngang; 320 không multi-column.
- [ ] Contrast body ≥4.5:1, large ≥3:1.
- [ ] Print ≤6 trang A4; không ảnh/màu.
- [ ] Existing 574 tests + test layout mới xanh; CI xanh.

---

## 6. Plan outline (để bạn lên plan)

### Phase 0 — Chốt design contract
- Chọn hướng A (editorial review) hay B (image-led).
- Chốt palette 2+2, type scale 5 size, grid 12 cột.
- Viết `docs/magazine-ui-contract.md` 1 trang.

### Phase 1 — Shell + top fold
- Masthead, nav, hero 7/5, Most Read.
- Bỏ full-width background section.
- Test 320/768/1024/1440.

### Phase 2 — Section module
- Section head rule 2px + number.
- Lead 7/5, brief 2 cột, measure 45–75ch.
- Section brief 280–320 ký tự; refs chip line.
- Test content 30 item, 3 section.

### Phase 3 — Image system
- OG 16:9, paper figure 4:3.
- Fallback typographic plate chỉ 1 feature.
- Test 6 ảnh + 24 no-image.

### Phase 4 — Color/type/dark/print
- Token hóa palette, type scale.
- Dark contrast.
- Print 2 cột, ≤6 trang.

### Phase 5 — QA
- Screenshots 320/768/1024/1440, light/dark.
- Contrast, line length, page height, print.
- Test suite + CI.

---

## 7. Quyết định còn mở

1. **Chọn A hay B?** Mình khuyến nghị A vì dữ liệu ảnh thật chỉ 6/30 và phần lớn là figure paper. B chỉ đẹp nếu bạn đầu tư thêm ảnh/art direction.
2. **Có giữ 3 màu section không?** Nên giữ nhưng chỉ làm rule/label, không background. Nếu muốn tối giản hơn, dùng một accent đỏ và section đánh số.
3. **30 item hay ít hơn?** Giữ 30 theo yêu cầu hiện tại; nếu muốn magazine “thở” hơn, có thể giảm feature/brief và đưa phần còn lại vào index.

---

## 8. Nguồn

- Nielsen Norman Group, *Visual Hierarchy in UX: Definition* (2021): https://www.nngroup.com/articles/visual-hierarchy-ux-definition/
- WIRED, *Welcome to the New WIRED* (2015): https://www.wired.com/2015/03/our-new-site/
- InPublishing, *Atlantic website redesigned* (2015): https://inpublishing.co.uk/articles/the-atlantic-yesterday-unveiled-a-redesign-of-theatlanticcom-5596
- The New York Times, *The New York Times Redesign*: https://www.nytimes.com/redesign/
- Butterick’s Practical Typography, *Line length*: https://practicaltypography.com/line-length.html
- web.dev, *Typography*: https://web.dev/learn/design/typography
- W3C WAI, *Understanding SC 1.4.3 Contrast (Minimum)*: https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html
- Screenshot/metrics hiện tại: `output/qa/real-1280.png`, `real-980.png`, `real-820.png`, `real-760.png`, `real-dark-1280.png`, `real-A4.pdf`
