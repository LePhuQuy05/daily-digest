# Newsroom Front Page — Kế hoạch redesign UI Daily AI Digest

> **Trạng thái:** proposal · 2026-11-19
> **Thay thế:** `docs/ui-redesign-plan.md` (dark reading room) — phần interaction layer,
> token architecture và print vẫn được kế thừa.
> **Research nền:** `docs/research/news-ui.md` + ảnh tham chiếu trong
> `docs/research/news-ui/` (NYT & VnExpress, desktop/mobile).

## 0. TL;DR

Chuyển popup từ **"dark reading room"** sang **"buổi sáng đọc báo AI"**: một
**newsroom front page** nền giấy sáng, kết hợp:

- **NYT bones** — masthead serif, grid 12 cột, headline hierarchy, hairline rules,
  rail "Most Popular", rất ít màu.
- **VnExpress energy** — một accent đỏ, section fronts dày, numbered rail, nhịp
  đọc nhanh, cảm giác "có tin mới".

Không đổi backend/ranking. Giữ nguyên bridge feedback/ask, blob `digest-data`,
pinned "Nhìn lại", print PDF, offline-first và các class/chuỗi bị test khóa.
**Không có ảnh photos ở v1** — đây là text-first broadsheet; ảnh OG/thumbnail là
phase sau (xem §10).

---

## 1. Mục tiêu / không mục tiêu

### Mục tiêu
- Popup 980×1080 mở ra giống **trang nhất báo**, không phải danh sách card.
- Above-the-fold thấy ngay: masthead + dateline + section nav + briefing +
  hero headline + rail.
- 12 câu chuyện có **3 tầng hierarchy** rõ: hero → section lead → brief.
- Một accent đỏ duy nhất; section identity bằng rule/label, không bằng rainbow card.
- Giữ nguyên chức năng: like/dislike/save, ask drawer, pinned, theme toggle, print PDF.
- Offline 100%: không CDN, không Google Fonts, không ảnh remote.

### Không làm trong v1
- Không fetch/cache ảnh OG, không thumbnail tự sinh.
- Không đổi model/ranking/prompt; không thêm trang con hay routing.
- Không dùng React/Tailwind/shadcn (app là plain CSS + Jinja2 một file).
- Không infinite scroll, ads, paywall, newsletter popup.

---

## 2. Học gì từ NYT & VnExpress

> **Giới hạn capture:** `nytimes-desktop.png` bị **DataDome chặn** ("You have
> been blocked..."), nên các quan sát NYT dựa trên header hiển thị + public
> design language; **VnExpress desktop/mobile là reference thật** (số đo chi tiết
> trong `docs/research/news-ui.md`). Không overclaim số đo NYT từ screenshot bị chặn.
>
> **Bằng chứng chính (VnExpress CSS):** `en_general.css` v367 — `#9F224E` xuất
> hiện **107 lần**; body `Montserrat 13px/16px`; deck `.lead_news_site`
> `Georgia 14px/19.5px #4F4F4F`; hairline `#E5E5E5`; rail `.item_most_read`
> border `#F1F1F1`, `padding-left:30px`. Tỉ lệ top fold 50/26/24 đo từ screenshot.

| Thành phần | NYT | VnExpress | Chuyển vào digest |
|---|---|---|---|
| Masthead | Wordmark blackletter giữa trang, double rule, dateline hai bên | Logo đỏ, utility bar (date/thời tiết), nav ribbon | Wordmark serif giữa + stamp đỏ "AI"; dateline + stats rule |
| Grid | Nhiều cột, hero lớn + rail, hairline dọc | Top fold bất đối xứng **~50/26/24**; section front 2 cột; hairline `#E5E5E5` | Top fold **64/36** (hero + rail briefing); section 5/7; 980px brief 1 cột |
| Headline | Serif, phân tầng rất mạnh, ít màu | Sans đậm 18–22px; deck serif 14–16px | Serif hero/section lead (NYT bones) + sans meta; brief 17px serif |
| Meta | Sans nhỏ, xám, byline/time | Meta 12px `#757575` | `source · points · citations` text; dùng `#6B6B6B` để đạt AA |
| Accent | Đen/trắng + xanh link; đỏ chỉ breaking | **Crimson `#9F224E`** cho nav, trending, hero mobile, underline section | Một crimson `#9F224E` + ink; link navy; danger tách riêng |
| Card | Không card, không shadow; rule + whitespace | Không card; hairline 1px; không radius/shadow | Bỏ card/shadow/left-bar; rule + whitespace |
| Rail | "Most Popular" numbered list | "Most Read" 1–5, số lớn `#BDBDBD` | "Trong ngày" box + "Nhìn lại" + "Đọc nhiều" 01–03 |
| Motion | Gần như không; hover underline | Gần như không; hover đỏ | Bỏ shimmer/stagger; hover 150ms |
| Ảnh | Hero image lớn | Hero image lớn (desktop/mobile) | **Không có** → text-first, source mark, section stamp |

**Số đo chính** (chi tiết + selector trong `docs/research/news-ui.md`):

- **VnExpress:** container **1260px** + margin 90px ở 1440; lead **640px**,
  rail **300px**, nhịp dọc **20px**. Body Montserrat **13/16**; lead headline
  **Montserrat 20/24 700 #444**; deck **Georgia 16/20.8 #4F4F4F**; accent
  **#9F224E**; rules `#E5E5E5`/`#F1F1F1`.
- **NYT (CSS proxy `r.jina.ai`, live bị DataDome chặn):** grid **14 cột**,
  span 5/7/9/14; Cheltenham hero **2rem/1.15 300**; card **1.375rem/1.15 700**;
  Imperial deck **1rem/1.39**; Franklin kicker **.6875rem/1.25 500 +.1em**;
  meta **.625rem #727272**; palette `#121212/#5A5A5A/#727272/#EBEBEB`,
  accent `#346EB7`.
- Scale 980px của VnExpress ≈ **600 lead + 300 rail + 32 gutter** — khớp grid
  8/4 của digest.

**5 nguyên lý rút ra**

1. **Hierarchy bằng typography, không bằng card.** Cỡ chữ + vị trí + rule làm nên
   trang báo; card bo tròn + shadow làm nên dashboard.
2. **Một accent.** Đỏ chỉ dành cho kicker/section/active/hover; không tô màu 3 section.
3. **Grid có nhịp.** Hero lớn, section lead vừa, brief dày, rail số — mắt không
   quét một cột đều đều.
4. **Rule thay cho border card.** Hairline 1px + double rule dưới masthead tạo
   cảm giác giấy in, rẻ và sạch.
5. **Motion gần bằng 0.** "Không chán" đến từ bố cục và mật độ thông tin, không
   từ animation.

**Không copy:** hero image full-bleed (không có ảnh), ads/paywall, nav 10 mục,
mega-menu, infinite scroll, màu đỏ cho mọi thứ.

---

## 3. Định hướng thiết kế

### 3.1 "Text-first broadsheet"

Một trang nhất không ảnh vẫn có thể đẹp nếu:
- Hero dùng **headline lớn + deck + summary**, có số thứ tự/section stamp làm
  điểm neo thị giác.
- Brief có **source mark** (arXiv/HN/HF) và meta text, không chip.
- Rail có **số 01/02/03** lớn, giống "Most Popular".
- Section front có **rule màu 2px** + số section, tạo nhịp màu tiết chế.

### 3.2 Design tokens (light newsprint + night edition)

```css
:root {
  /* paper & ink — warm newsprint, không phải trắng dashboard */
  --paper: #FBFAF7;
  --paper-warm: #F3F1EB;      /* briefing box, rail box */
  --ink: #1A1A1A;
  --ink-2: #4F4F4F;
  --ink-3: #6B6B6B;           /* #757575 của VnExpress fail AA trên warm paper */
  --rule: #E5E5E5;
  --rule-strong: #1A1A1A;

  /* brand — VnExpress crimson */
  --red: #9F224E;
  --red-ink: #7A1839;
  --danger-ink: #B91C1C;      /* tách khỏi brand để .failed không lẫn accent */
  --link: #1A4F8B;

  /* section identity — CHỈ decorative 2px tick, không dùng làm text */
  --sec-papers: #0F766E;
  --sec-news: #B45309;
  --sec-tools: #047857;

  /* type */
  --font-serif: "Newsreader", Cambria, "Times New Roman", Georgia, serif;
  --font-sans: "Segoe UI Variable Text", "Segoe UI", system-ui, -apple-system, Roboto, sans-serif;

  /* semantic aliases — giữ tên cũ để giảm test churn */
  --bg: var(--paper);
  --bg-raised: var(--paper);
  --bg-overlay: var(--paper-warm);
  --text-1: var(--ink);
  --text-2: var(--ink-2);
  --text-3: var(--ink-3);
  --accent: var(--red);
  --accent-strong: var(--red-ink);
  --accent-soft: rgba(159, 34, 78, 0.08);
  --border: var(--rule);
  --border-strong: var(--rule-strong);
  --danger: var(--danger-ink);
  --ring: var(--red);
  --card-radius: 2px;       /* chỉ dùng cho button/input, không cho card */
  --card-gap: 24px;
  --shadow-1: none;
  --shadow-2: none;

  /* shape */
  --radius-btn: 2px;
  --content-max: 1040px;
  --gutter: 24px;
}

[data-theme="dark"] {           /* Night edition */
  --paper: #121212;
  --paper-warm: #1A1A1A;
  --ink: #F2EFE9;
  --ink-2: #C9C4BC;
  --ink-3: #9A958D;
  --rule: #2E2E2E;
  --rule-strong: #F2EFE9;
  --red: #FF6B6B;
  --red-ink: #FF9A9A;
  --danger-ink: #FF8A8A;
  --link: #8CC8FF;
  --accent-soft: rgba(255, 107, 107, 0.12);
  --sec-papers: #5EEAD4;
  --sec-news: #FCD34D;
  --sec-tools: #6EE7B7;
}
```

- **Default = light newsprint**, không auto theo system. Toggle "Night edition"
  lưu `localStorage`; lý do: bản sắc trang báo là giấy sáng, và user hiện tại
  đang thấy dark "chán".
- **Một accent crimson `#9F224E`** (đúng VnExpress) cho kicker/nav active/hover/
  section underline. Danger `.failed` dùng `#B91C1C` riêng, không lẫn brand.
- Section colors chỉ xuất hiện ở **2px decorative tick** (không phải text);
  amber `#B45309` trên paper-warm chỉ 4.45:1 nên tuyệt đối không dùng làm chữ.
- **Contrast audit (2026-11-19):** crimson 7.15:1 on paper / 7.47 on white;
  crimson-ink 9.97; ink 16.67; ink-2 7.85; ink-3 5.11; link 7.94; danger 6.20;
  night ink 16.32, night ink-3 6.30, night red 6.75; VnExpress meta `#757575`
  fail 4.41 trên warm → dùng `#6B6B6B`. Tất cả text pair ≥ 4.5:1 (pass AA).

### 3.3 Typography scale

| Vai trò | Size / line-height | Weight | Ghi chú |
|---|---|---|---|
| Masthead wordmark | 40–44 / 1.0 | 700 serif | letter-spacing −0.03em |
| Dateline / kicker | 11 / 1.4 | 700 sans | uppercase, +0.10em |
| Hero headline | 36–40 / 1.08 | 700 serif | clamp(30px, 4.2vw, 40px) |
| Section title | 22–24 / 1.2 | 700 serif | số section bên trái |
| Section lead | 24–26 / 1.2 | 700 serif | 1 item mỗi section |
| Brief headline | 17–18 / 1.3 | 600 serif | 2–3 dòng |
| Rail headline | 15.5–16 / 1.35 | 600 serif | numbered list |
| Deck / why | 16 / 1.5 | 400 serif | `--ink-2`; hero 17px |
| Body / summary | 14.5 / 1.55 | 400 sans | clamp 3–5 dòng |
| Meta | 12 / 1.4 | 500 sans | `source · points · citations` |
| Action label | 12 / 1 | 600 sans | icon 16px |

- Serif: **Cambria / Times New Roman** mặc định — đã kiểm tra glyph tiếng Việt
  (`ạộữếệởỹụ`): Cambria OK, Times New Roman OK, **Georgia thiếu glyph** nên
  không dùng Georgia làm serif chính. Nếu muốn sát NYT hơn, bundle **Newsreader**
  (OFL, Vietnamese subset) dưới dạng **data URI trong template** — không import
  Google Fonts, vẫn offline/single-file. Stack: `"Newsreader", Cambria,
  "Times New Roman", Georgia, serif`.
- Không dùng `font-weight: 650` với font system không variable; dùng 600/700 thật.
- **Deck dùng serif** (Cambria/Times) theo VnExpress Georgia + NYT Imperial;
  summary/body dùng sans. Chỉ 2 family — không copy 4 font của VnExpress.
- **Hero weight:** NYT dùng 300 (nhẹ), VnExpress 700 (đậm); popup chọn
  **600–700** để hierarchy đủ mạnh ở 980px.
- **Body size:** VnExpress 13px rất dày; popup dùng **14.5–15px** để đọc thoải
  mái hơn, vẫn giữ density bằng line-height 1.5–1.55.

### 3.4 Grid & spacing

- `.wrap { max-width: 1040px; padding: 0 24px; }` — trong popup 980px, content
  thực tế 932px.
- 12 cột, gap 24px.
- Top fold: **hero 8/12 (~64%) + rail 4/12 (~36%)**; rail chứa briefing
  "Trong ngày" + "Nhìn lại" (nếu có) + "Đọc nhiều" + nguồn.
- Section front: `grid-template-columns: 5fr 7fr`; section chẵn đảo chiều
  (lead bên phải, briefs bên trái) để tạo nhịp.
- **Quy tắc ≥280px:** không để cột text nào hẹp hơn 280px. Vì vậy brief grid
  **2 cột chỉ bật khi content ≥1100px**; ở 980px briefs là **1 cột**.
- Kích thước thực tế (gap 24; section gap 28; brief gap 20):

| Window | Content | Hero (8/12) | Rail (4/12) | Section lead (5/12) | Briefs (7/12) | Brief 1 cột | Brief 2 cột |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 980 | 932 | 613 | 295 | 377 | 527 | 527 | — |
| 1120 | 1040 | 685 | 331 | 422 | 590 | 590 | 285 |

- Khoảng cách module: 32px; trong story: 6–10px; section header → content: 16px.
- Breakpoints: 1100 / 980 / 760 / 520. Dưới 760px: 1 cột, rail xuống dưới hero,
  nav scroll ngang; hero mobile dùng block nền `--paper-warm` như VnExpress.

### 3.5 Shape, rule, shadow

- **Không card.** Story là block trần, phân tách bằng `border-top: 1px solid var(--rule)`.
- Bo góc chỉ 2px cho button/input; không bo card.
- Không `box-shadow` cho story/rail. Chỉ có thể dùng 1 shadow rất nhẹ cho sticky
  nav nếu cần, tốt nhất là border-bottom.
- Masthead: `border-top: 3px double var(--rule-strong)` + `border-bottom: 1px solid var(--rule)`.
- Section header: rule 1px full-width phía trên; label có **gạch chân crimson 3px**
  (ngắn, như VnExpress), không dùng section color làm underline.

### 3.6 Icon & visual mark

- Giữ bộ SVG hiện có (thumb, bookmark, pin, check, send, moon/sun), thêm:
  `i-arrow-right` (link "Xem tất cả"), `i-chevron` (nav mobile), `i-close` (ask).
- Source mark: chữ **arXiv / HN / HF** trong small caps (ink), hoặc ô 18×18
  ink/paper với chữ cái đầu + optional 2px section tick; không logo remote.
- Section stamp: số `01/02/03` **18px** cạnh section title (không phóng to như
  magazine); rail "Đọc nhiều" mới dùng số lớn 28–32px màu rule.
- Không emoji.

### 3.7 Motion & freshness

- Hover headline: `text-decoration: underline; text-underline-offset: 3px;` 150ms.
- Nav active: underline 2px đỏ, đổi khi scroll (IntersectionObserver).
- Không shimmer, không gradient, không stagger reveal.
- `prefers-reduced-motion`: tắt smooth scroll, transition; dots "đang nghĩ" vẫn
  nhấp nháy nhẹ (chức năng) hoặc đứng yên nếu muốn strict.
- **Cảm giác "mới" đến từ tín hiệu tĩnh, không từ animation:** tag đỏ `MỚI` cho
  item arXiv mới trong ngày, dateline "CẬP NHẬT 07:00", số thứ tự rail. Không
  ticker giả, không "breaking news" giả.

---

## 4. Information architecture & wireframe

### 4.1 Desktop (popup 980px)

```
┌──────────────────────────────────────────────────────────────────┐
│  [AI]   DAILY AI DIGEST                                  ☾/☀    │
│  THỨ NĂM, 19.11.2026 · BẢN TIN AI · 12 CÂU CHUYỆN              │
│ ════════════════════════════════════════════════════════════════ │
│  Tổng hợp   Nghiên cứu   Công nghệ   Công cụ   Nhìn lại          │
├───────────────────────────────────────────┬──────────────────────┤
│  CÂU CHUYỆN CHÍNH                        │  TRONG NGÀY          │
│  "It's Just a Small Weapon": ...         │  TỔNG HỢP HÔM NAY    │
│  Deck: vì sao bài này đáng đọc...        │  01 RL cho agent...  │
│  Summary 4–5 dòng...                     │  02 Hạ chi phí...    │
│  arXiv · 1.2k citations · MỚI            │  03 → Đáng đọc...    │
│  [like] [save] [Hỏi biên tập]            │  ─────────────────   │
│                                          │  ĐỌC NHIỀU           │
│                                          │  01 ... 02 ... 03 ...│
│                                          │  Nguồn: arXiv 11 · HN│
├───────────────────────────────────────────┴──────────────────────┤
│  01  RESEARCH PAPERS                                 11 stories  │
│  ─────────────────────────────────────────────────────────────── │
│  Lead headline 24–26px                 │  Brief 1  │ Brief 2     │
│  deck + summary                        │  meta     │ meta        │
│  meta                                  │  Brief 3  │ Brief 4     │
│                                        │  Brief 5  │ Brief 6     │
│                                        │  ───────────────────    │
│                                        │  More: Brief 7 · 8 · 9  │
├──────────────────────────────────────────────────────────────────┤
│  02  TECH NEWS (1 item)                                          │
│  Launch HN: Maritime (YC F26) — full-width band lead, 26px       │
├──────────────────────────────────────────────────────────────────┤
│  03  TOOLS & RELEASES — hôm nay không có mục nào                 │
├──────────────────────────────────────────────────────────────────┤
│  Footer: nguồn · cập nhật · in PDF                               │
└──────────────────────────────────────────────────────────────────┘
```

> Nếu có `pinned`, box "NHÌN LẠI" chèn **trên** "ĐỌC NHIỀU". Nếu không, rail
> chỉ có "TRONG NGÀY" + "ĐỌC NHIỀU" + nguồn — không render box rỗng.
>
> Wireframe vẽ ở **1120px** (brief 2 cột). Ở **980px**, brief là **1 cột**;
> rail vẫn 4/12 (~295px). Hero mobile dùng nền `--paper-warm` như VnExpress.

### 4.2 Mobile / popup hẹp (≤760px)

```
masthead
dateline
nav (scroll ngang, sticky)
hero (warm block, như VnExpress mobile)
briefing box "Trong ngày"
most read (→ Nhìn lại nếu có → nguồn)
section 01 (lead → briefs 1 cột)
section 02 ...
footer
```

### 4.3 Mapping nội dung → module

| Nội dung | Module | Ghi chú |
|---|---|---|
| `overview` | Briefing box "Trong ngày" trong rail | 3–4 điểm numbered; câu cuối "Đáng đọc nhất" có → |
| `ranked[0]` | Hero "Câu chuyện chính" | Không lặp lại ở section front |
| `ranked[1:]` theo section | Section front: lead + briefs | Section lead = item đầu tiên còn lại |
| `pinned` | Rail "Nhìn lại" | Wrapper giữ `class="block pinned-block"` |
| `ranked[1:4]` | Rail "Đọc nhiều" | Chỉ link anchor, **không render lại card** |
| `counts`, `total` | Dateline + section headers | "12 câu chuyện · 3 chuyên mục" |
| `degraded`, `sources_failed`, `notice` | Thin status strip dưới nav | Không chiếm hero |
| `mode`, `model_name` | Footer/dateline nhỏ | "Biên tập: heuristic/LLM" |

---

## 5. Data model & render changes

### 5.0 Content reality (dry-run trên digest thật 2026-11-19)

Chạy thử mapping trên `output/latest.html`: **11 papers, 1 tech news, 0 tools,
0 pinned**. Đây là phân bố thường gặp (AI papers áp đảo), nên front page phải
**content-aware**, không chia 3 section bằng nhau:

| Section | Items | Cách render |
|---|---:|---|
| papers | 11 (1 hero + 1 lead + 9 briefs) | Lead 5 cột + brief grid 2 cột ở 1120 (6 briefs) + "More" (3); ở 980 brief 1 cột |
| tech_news | 1 | Full-width **band lead** (không phải 5/7 split rỗng) |
| tools_releases | 0 | Slim empty note, không chiếm nửa trang |
| pinned | 0 | Ẩn box "Nhìn lại"; rail có "Trong ngày" + "Đọc nhiều" + nguồn |

Quy tắc render section front theo số item còn lại:
- `0`: 1 dòng empty note + rule.
- `1`: full-width band lead (headline 26px, summary 3 dòng) — không có cột brief rỗng.
- `2–3`: lead 5 cột + briefs 7 cột (1 cột brief).
- `>=4`: lead 5 cột + brief grid 2 cột (tối đa 6 briefs) + "More" list
  (phần còn lại, dense 1 cột). Tất cả item vẫn hiển thị, không cắt.

### 5.1 `build_front_page(ranked, pinned=())` trong `daily_digest/render.py`

```python
@dataclass(frozen=True)
class SectionFront:
    key: Section
    title: str
    lead: RankedItem | None
    briefs: tuple[RankedItem, ...]
    total: int          # tổng item trong section, gồm cả hero nếu hero thuộc section

@dataclass(frozen=True)
class FrontPage:
    lead: RankedItem | None
    sections: tuple[SectionFront, ...]
    most_read: tuple[RankedItem, ...]
    source_counts: dict[str, int]   # cho rail "Nguồn hôm nay"
```

Quy tắc:
1. `lead = ranked[0]` (ranked đã sort theo score; **không re-rank ở view**).
2. Bỏ hero khỏi nhóm section; mỗi section giữ thứ tự gốc:
   `lead = items[0]`, `briefs = items[1:]`.
3. `most_read = ranked[1:4]` — chỉ dùng để render link `#story-<uid>`, không
   render lại card (tránh trùng `data-feedback`, tránh double feedback).
4. `pinned` vẫn là list dict từ pipeline; pipeline đã loại uid trùng ranked.
   Nếu `pinned` rỗng: ẩn box "Nhìn lại", rail hiện "Đọc nhiều" + "Nguồn hôm nay".
5. `total` của section = tổng item ban đầu trong section (gồm hero nếu hero
   thuộc section đó) để số trên header không nhảy. Header ghi "11 stories";
   hero là item đầu của section được đẩy lên trên, nên section front hiển thị
   10 item còn lại — thêm chú thích nhỏ "1 bài chính ở trên" nếu cần.
6. `source_counts` = đếm source trong ranked (arXiv/HN/HF) cho rail "Nguồn".
7. Không mutate `ranked`/`pinned`; hàm pure, test được. `pinned` truyền vào chỉ
   để lọc uid trùng ranked (defensive), không đưa vào `FrontPage`.

### 5.2 Edge cases
- `ranked=[]`: không hero; briefing nếu có; hiện empty state full-width; rail
  "Nguồn" nếu có; pinned nếu có.
- Section 0 item: hiện slim empty note (giữ test empty state cũ, đổi class).
- Section 1 item và item đó là hero: section front không còn item → hiện dòng
  "Bài chính ở trên" link tới hero anchor, không lặp card.
- **Section skew (thực tế):** 11 papers / 1 tech / 0 tools — dùng rule §5.0;
  papers grid 2 cột + More, tech band, tools note. Không chia đều 3 cột.
- `pinned` rỗng: ẩn "Nhìn lại", không render wrapper rỗng; rail vẫn có "Đọc nhiều"
  + "Nguồn hôm nay".
- `pinned` trùng ranked (defensive): lọc trong `build_front_page`/render; test.
- 1 item toàn digest: hero only + empty sections; không crash.
- Overview 1 câu: briefing 1 điểm, không spotlight rỗng.

### 5.3 Template context
- Thêm `front_page` vào `render_digest()`; giữ `sections`, `counts` cho
  backward-compat (có thể bỏ sau khi template chuyển xong).
- Không đổi signature public của `render_digest` (trừ optional).
- `digest_data` blob giữ nguyên 100%.

---

## 6. Component specs

### 6.1 Masthead
- `<header class="masthead">` (không sticky; sticky là nav).
- Wordmark giữa: stamp đỏ 26×26 chữ "AI" + `Daily AI Digest` serif 42px.
- Trên wordmark: rule double 3px; dưới: dateline + double rule mảnh.
- Theme toggle đặt góc phải dateline, icon 18px, không viền card.

### 6.2 Dateline
- `THỨ NĂM, 19.11.2026 · BẢN TIN AI · 12 CÂU CHUYỆN` — 11px uppercase sans,
  `--ink-3`, letter-spacing .10em.
- Bên trái: "Biên tập: LLM (glm-5.3)"; bên phải: "Cập nhật 07:00" (nếu có).
- Ngày format từ `YYYY-MM-DD` → `19.11.2026`; thứ lấy từ Python (thêm
  `date_long` context) hoặc bỏ thứ ở v1.

### 6.3 Section nav (sticky)
- `<nav class="section-nav" aria-label="Chuyên mục">` sticky top 0, height 42px,
  nền `--paper`, border-bottom 1px.
- Links: `Tổng hợp` (#top), `Nghiên cứu` (#papers), `Công nghệ` (#tech-news),
  `Công cụ` (#tools-releases), `Nhìn lại` (#pinned).
  **Link "Nhìn lại" chỉ render khi `pinned` có item** — không để anchor chết.
- 12px uppercase 700, gap 22px; active: 2px red underline; hover: red.
- Mobile: overflow-x auto, ẩn scrollbar; không wrap.
- **Không làm "Trending" keyword bar ở v1** vì `overview` là free text, chưa có
  structured topics; thay bằng section nav + tag `MỚI`. Nếu sau này LLM trả
  topics, thêm strip dưới nav (không fake ticker).

### 6.4 Briefing box "Trong ngày" (rail)
- Nằm trong **rail 4/12**, `background: var(--paper-warm)`, border-top **3px
  crimson**, padding 14–16px; không full-width.
- Kicker `TỔNG HỢP HÔM NAY` 10.5px crimson; label "Trong ngày" serif 20–22px;
  danh sách numbered `01/02/03` 13.5px; câu cuối "Đáng đọc nhất" in đậm + mũi
  tên đỏ.
- Tối đa 3–4 điểm, clamp; không gradient, không shimmer, không drop-cap, không card.
- Giữ `.overview` class + `.briefing` để test cũ dễ chuyển; đây là box duy nhất
  (cùng "Nhìn lại") được dùng nền `--paper-warm`.

### 6.5 Hero
- Kicker "CÂU CHUYỆN CHÍNH" đỏ; headline 38px serif; deck (why) 17px **serif**;
  summary 15px clamp 5 dòng; meta text; actions.
- **Mobile (≤760px):** hero là một block nền `--paper-warm` có padding, giống
  VnExpress mobile; headline vẫn ink, kicker crimson; không full-bleed ảnh.
- Tag đỏ `MỚI` cho item arXiv mới trong ngày (tín hiệu tĩnh, không animation).
- Có thể thêm stamp section bên phải headline (số 01 lớn, màu rule) — optional.
- Không ảnh; khoảng trắng là "ảnh".

### 6.6 Section front (content-aware)
- Header: `01` **18px** (crimson/ink) + `RESEARCH PAPERS` **22px serif** +
  count + link "Xem tất cả" (anchor) bên phải; rule 1px full-width phía trên;
  label có **gạch chân crimson 3px** (ngắn), không dùng section color.
- **Variant theo số item còn lại** (sau khi lấy hero):
  - `0`: một dòng empty note + rule, không chiếm nửa trang.
  - `1`: full-width **band lead** — headline 26px, summary 3 dòng, không cột brief rỗng.
  - `2–3`: grid 5/7 — lead trái, briefs phải (1 cột).
  - `>=4`: grid 5/7 — lead trái; phải là brief grid **2 cột chỉ khi ≥1100px**,
    còn 980px là **1 cột** + "More" list dense cho phần còn lại. Tất cả item vẫn hiển thị.
- Section chẵn đảo chiều (lead phải, briefs trái) để tạo nhịp; riêng variant 1
  item luôn full-width.
- Brief: border-top 1px rule giữa các item; headline 17px; meta; summary 2–3 dòng.
- Section id: `papers`, `tech-news`, `tools-releases` để nav anchor.

### 6.7 Rail
- `<aside class="rail">` — không sticky trong popup; đặt cạnh hero (4/12).
- **Box "TRONG NGÀY"** (briefing) ở trên: nền `--paper-warm`, border-top 3px
  crimson, 3 numbered points (xem §6.4).
- Box "NHÌN LẠI" (chỉ khi `pinned`): header uppercase + count; danh sách numbered
  1..n; mỗi item headline 15.5px + meta; nếu bridged, nút check nhỏ "Đọc xong"
  ở cuối item (giữ `data-feedback`).
- Box "ĐỌC NHIỀU": top 3 link anchor; số 01/02/03 lớn màu rule; không feedback
  (tránh trùng).
- Dòng "Nguồn: arXiv 11 · HN 1 · HF 0" 11px cuối rail.
- Wrapper pinned giữ `class="block pinned-block"` (test lock).

### 6.8 Story variants
- `hero`, `section-lead`, `brief`, `rail-item`.
- Tất cả dùng chung `.story` + modifier; headline là `<h3><a>` (semantic).
- Title link giữ `target="_blank" rel="noopener noreferrer"` và `safe_href`.
- `id="story-{{ uid }}"` trên `<article>` để rail link tới.
- `data-uid` giữ trên article.
- `.summary.ai` giữ đúng class (test khóa) + label "AI SUMMARY" nhỏ phía trên.
- `.why` giữ class; style như deck **serif 16px**, không có "→ " prefix
  (hoặc giữ arrow nhỏ).

### 6.9 Feedback & ask
- Actions: icon 16px, hit area 28px, transparent, border none; hover red;
  `.act.done` fill đỏ + icon trắng; `.act.failed` đỏ.
- Không dùng chip/pill cho actions.
- Ask: chuyển thành `<details class="ask">` với `<summary>Hỏi biên tập</summary>`
  — chỉ hiện khi `body.bridged`; form input + submit bên trong; native keyboard
  accessible, không cần JS toggle.
- Giữ `body.bridged .bridge-only` và `data-ask` / `data-feedback`.
- Ask answer giữ `aria-live="polite"`, dots animation.

### 6.10 Footer
- 12px, rule-top, 2 cột: nguồn (arXiv/HN/HF) + "Biên tập bởi LLM/heuristic ·
  In PDF · Lưu trữ trong output/". Không code block nổi bật.

### 6.11 Empty / degraded
- Degraded: thin strip vàng/đỏ dưới nav, 12px, không phá layout.
- Empty section: 1 dòng "— hôm nay không có mục nào —" 13px, rule nhẹ.

### 6.12 Print
- `@page { size: A4; margin: 16mm; }`.
- Force `--paper: #FFFFFF; --paper-warm: #FFFFFF; --ink: #111111;` cho print;
  bỏ background tint (máy in không in nền).
- Masthead + dateline + briefing + hero; sections 2 cột; box "Nhìn lại" xuống
  cuối; bỏ "Đọc nhiều" (link rail vô nghĩa trên giấy); ẩn
  nav/actions/ask/theme/footer tương tác.
- `break-inside: avoid` cho story; `column-rule: 1px solid #CCC`.
- Mục tiêu: PDF trông như trang nhất báo, 2–3 trang A4.

---

## 7. Phases triển khai

| Phase | Scope | Files chính | Proof |
|---|---|---|---|
| **0. Research + chốt** | Đọc NYT/VnExpress, chốt 5 quyết định §10 | `docs/research/news-ui.md`, plan này | Ảnh tham chiếu + review |
| **1. Layout model** | `build_front_page()` + tests; không đổi UI | `render.py`, `tests/test_front_page.py` | pytest mới xanh; edge cases |
| **2. Newsroom shell** | Tokens light/night, masthead, dateline, nav, briefing, footer; bỏ gradient/shimmer; light default | `templates/digest.html.j2`, `tests/test_ui_tokens.py` | Ảnh popup light 980px; toggle night |
| **3. Front page modules** | Hero, rail, section fronts, 4 story variants; data binding; responsive 760/520 | template + `tests/test_news_layout.py` | Ảnh full page; đủ 12 item, không trùng |
| **4. Interaction + bridge** | Sticky nav active, hover underline, feedback states, ask `<details>`, focus, reduced motion | template + `tests/test_popup_bridge.py` | States screenshot; bridge smoke |
| **5. Print + a11y** | Print broadsheet, contrast audit, empty/degraded, 720px | template + tests | PDF; 720px screenshot; contrast pass |
| **6. Visual QA** | So sánh NYT/VnExpress, vision review, live smoke, pixel metrics | `output/*` | Score + artifacts; final report |

**Ước lượng:** 5–6 ngày làm việc tập trung (hoặc 3–4 session), mỗi phase shippable.

### Phase 1 test matrix (`tests/test_front_page.py`)

- Digest thật 12 item (11 papers / 1 tech / 0 tools): hero, section leads/briefs,
  `most_read`, `source_counts`, `total`.
- 1 item duy nhất: hero only, section fronts rỗng, không crash.
- 0 item: `lead=None`, tất cả sections rỗng, `most_read=()`, không crash.
- 2 item cùng section: lead + 1 brief.
- Section chỉ có hero: section front rỗng; template hiện "Bài chính ở trên".
- `pinned` trùng uid ranked: bị lọc, không render 2 lần.
- Không duplicate uid giữa hero + section leads + briefs.
- Thứ tự section/item giữ nguyên ranked order (không re-sort trong view).

---

## 8. Acceptance criteria

### Tự động
- **Baseline hiện tại: `uv run pytest` → 233 passed (2026-11-19).**
- `uv run pytest` xanh sau từng phase; test cũ pass trừ các CSS-string assertion
  được thay đúng theo thiết kế mới.
- Chuỗi bị khóa còn nguyên: `.bridge-only { display: none; }`,
  `body.bridged .bridge-only`, `pywebviewready`,
  `typeof window.pywebview.api.feedback`, `class="block pinned-block"`,
  `class="summary ai"`, `<script type="application/json" id="digest-data">`,
  `data-feedback`, `data-ask`.
- `build_front_page` tests: lead/section split, no duplicate uid, empty/1-item.
- CSS tests: light default, tokens, 12-col grid, no gradient/shimmer, no
  card shadow/left-bar, red accent, print rules, focus-visible, contrast ≥4.5.
- Offline: không `http` ngoài SVG xmlns, không CDN/font remote.

### Visual / manual
- **Before (current dark reading room):** `output/ui-live-dark.png`,
  `output/ui-live-light.png` — dùng để so sánh A/B sau Phase 3.
- Popup 980×1080: above-the-fold thấy masthead + nav + briefing + hero headline
  + rail (ít nhất tiêu đề đầu rail).
- 12/12 item hiển thị đúng section, không lặp, không mất feedback.
- 980px: brief **1 cột**, không cột text nào <280px; 1120px: brief 2 cột.
- Hero/section lead/brief phân biệt rõ trong 2 giây nhìn.
- Light và Night edition đều đọc tốt; không còn cảm giác "dashboard card".
- 720px: 1 cột, không horizontal scroll; nav scroll ngang.
- Feedback done/failed + ask dots hoạt động trong popup thật.
- PDF: masthead + hero + 3 section headers (kể cả empty note); 2–3 trang A4;
  không lộ UI bridge.
- `open --web`: không lộ bridge, exit 0.
- Vision model đánh giá "giống trang báo" ≥ 8/10 khi đặt cạnh reference.

---

## 9. Risks & trade-offs

| Risk | Mức | Giảm thiểu |
|---|---|---|
| **Không có ảnh** → khó giống VnExpress/NYT thật | Cao | Text-first broadsheet, source mark, section stamp, số lớn; nói rõ đây là "broadsheet" không phải "photo homepage"; ảnh OG ở phase sau |
| **NYT reference bị DataDome chặn** | TB | Chỉ VnExpress có số đo thật; NYT dùng public design language + header visible; ghi rõ limitation, không overclaim |
| Popup 980px hẹp cho grid báo | TB | 8+4 grid; brief 1 cột ở 980, 2 cột chỉ ≥1100; optional tăng `WINDOW_WIDTH` lên 1120 (không có test width) |
| Cột text <280px → title wrap xấu | TB | Rule ≥280px: brief 2 cột chỉ bật khi content ≥1100; 980 dùng 1 cột |
| Nhiều test CSS cũ sẽ fail | TB | Viết lại `test_ui_tokens.py` theo suite `TestNewsroom*`; giữ test behavior/bridge |
| Dark mode mất chất "báo" | TB | Night edition riêng (giấy đen ấm, ink trắng ngà), không dùng lại slate/violet |
| Font serif tiếng Việt | TB | Cambria/Times đã verify glyph; **Georgia thiếu glyph** nên không dùng làm serif chính; Newsreader optional phải có Vietnamese subset + data URI |
| Bốn font / font swap | TB | Chỉ 2 families (serif/sans); deck serif, meta sans; không copy Arial mobile swap của VnExpress |
| Overview dài 900 ký tự | TB | Briefing 3–4 điểm, clamp; giữ word-boundary truncation |
| **Section skew** (11 papers / 1 tech / 0 tools) | Cao | Content-aware variants §5.0/§6.6: papers grid 2 cột ở 1120 / 1 cột ở 980 + More, tech band, tools note; test với digest thật |
| Trùng item/feedback giữa hero, section, rail | Cao | `build_front_page` pure + test no-duplicate; rail chỉ link anchor |
| Print nhiều trang | TB | 2 cột, `break-inside: avoid`, test PDF thật |
| Scope creep sang ảnh/font | TB | Chốt "no photos v1", "system fonts v1"; phase sau |

---

## 10. Quyết định cần chốt (đề xuất mặc định)

1. **Theme mặc định:** ✅ **Light newsprint `#FBFAF7`** (giấy ấm), Night edition
   qua toggle. Không auto theo system. *(Nếu bạn muốn giữ dark mặc định, nói rõ.)*
2. **Ảnh:** ✅ **Không ảnh ở v1** — text-first broadsheet. VnExpress/NYT thật
   dùng ảnh hero; muốn sát hơn sẽ cần phase 2 fetch/cache OG image (network +
   storage + data URI). *(Đây là giới hạn lớn nhất của độ giống.)*
3. **Accent:** ✅ **Crimson `#9F224E`** (đúng VnExpress) + ink + link navy;
   danger `.failed` dùng `#B91C1C` riêng. Không dùng teal/amber/emerald làm màu
   card; section colors chỉ là decorative tick.
4. **Width:** ✅ Đề xuất **1120px** cho popup (grid thoáng hơn); nếu giữ 980px
   vẫn chạy với grid 8+4 và **brief 1 cột**. Không có test nào khóa width.
5. **Font:** ✅ **Cambria/Times New Roman hệ thống ở v1** (đã verify glyph tiếng
   Việt; Georgia thiếu glyph). Optional bundle **Newsreader** (OFL, Vietnamese
   subset, data URI) nếu visual QA thấy chưa đủ "NYT".

> Nếu bạn đồng ý 1–5, tôi bắt đầu **Phase 1** (layout model + tests) rồi
> **Phase 2** (newsroom shell) — không big-bang rewrite.

---

## 11. Liên kết

- Research: `docs/research/news-ui.md`
- Ảnh tham chiếu: `docs/research/news-ui/*.png`
- Plan cũ (dark reading room): `docs/ui-redesign-plan.md`
- Template hiện tại: `templates/digest.html.j2`
- Render/data: `daily_digest/render.py`, `daily_digest/pipeline.py`
- Bridge: `daily_digest/popup_bridge.py`, `tests/test_popup_bridge.py`
- UI tests hiện tại: `tests/test_ui_tokens.py`
