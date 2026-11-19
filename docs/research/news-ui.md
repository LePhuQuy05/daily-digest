# Research: News homepage DNA — NYT & VnExpress

> **Captured:** 2026-11-19 (headless Edge, desktop 1440×2400, mobile 390×844)
> **Screenshots:** `docs/research/news-ui/nytimes-desktop.png`,
> `vnexpress-desktop.png`, `vnexpress-mobile.png`
> **Dùng cho:** `docs/news-ui-redesign-plan.md`

## 0. TL;DR

- **VnExpress là reference thật** (HTTP 200, homepage đầy đủ): 3 cột top fold
  bất đối xứng, hairline 1px, **một crimson `#9F224E`**, sans headline +
  **Georgia serif deck 14px**, rail "Most Read" 1–5.
- **NYT desktop bị DataDome chặn** — screenshot chỉ là trang block; không có số
  đo homepage. Các nhận xét NYT dưới đây là *public design language*, không phải
  measured từ capture này.
- Bài học chuyển vào digest: flat paper + hairline rules + một accent crimson +
  asymmetric top fold + numbered rail; **không** card bo tròn/shadow, **không**
  3 cột đều ở 980px, **không** ảnh (v1).

## 1. Capture & limitations

| Site | URL | Kết quả | Ghi chú |
|---|---|---|---|
| VnExpress | https://e.vnexpress.net/ | 200, 278.710 bytes HTML | Homepage thật; CSS `en_general.css` fetch được |
| NYT | https://www.nytimes.com/ | DataDome block | "You have been blocked from The New York Times because we suspect that you're a robot" |

- VnExpress CSS chính: `https://s.vnecdn.net/english/c/v367/en_general.css`
  (315.020 bytes sau khi giải nén, fetch 2026-11-19). Các selector dưới đây
  trích từ file này.
- Tỉ lệ cột top fold (50/26/24) là **đo từ screenshot**, không phải CSS.
- NYT: không đo được grid/typography homepage; chỉ thấy trang block + một
  headline serif căn giữa. Không dùng số đo NYT trong plan.

## 2. VnExpress — primary source

### 2.1 Screenshot observations

- **Masthead + utility bar:** logo đỏ, hàng ngày/thời tiết, nav ribbon đỏ đậm.
- **Top fold 3 cột bất đối xứng ~50/26/24:** lead story lớn bên trái; cột giữa
  2 story text-only; cột phải **Most Read 1–5**.
- **Section fronts 2 cột** phía dưới; headline + deck + meta, không card.
- **Hairline** 1px phân tách; nền trắng; không bo góc, không shadow.
- **Mobile:** masthead gọn, dateline/thời tiết full-width; hero block nền
  `#F7F7F7` với headline crimson + deck 5 dòng; story rows gọn bên dưới.

### 2.2 Typography (CSS thật)

| Vai trò | CSS | Nguồn |
|---|---|---|
| Body | `body { color:#333; font-family:Montserrat,sans-serif; font-size:13px; line-height:16px; background:#fff; }` | `en_general.css` |
| Lead headline | `h4.title_news_site` — Montserrat **20px/24px 700 #444** (computed) | screenshot + CSS |
| Standard title | `.title_news_site { font-size:16px; font-weight:700; line-height:1.2; letter-spacing:-1px; }` | `en_general.css` |
| Deck / sapo | `.lead_news_site { font-family:Georgia; font-size:14px; line-height:19.5px; color:#4f4f4f; }`; lead computed **16px/20.8px** | `en_general.css` |
| Section label | Montserrat **16px 700** | computed |
| Trending | Montserrat **16px/20px 300** | computed |
| Meta | `#757575` (30 occurrences) | `en_general.css` |
| Mobile H1 | **28px/1.31**; body mobile chuyển `Arial 14px` (`body.body_mobile`) | computed |

- **Cặp font thật:** Montserrat (sans) cho headline/body + **Georgia** cho deck.
  Không phải Merriweather cho headline; `Merriweather` chỉ là @font-face riêng
  (subscription box) — `Merriweather-woff2.css` 164.094 bytes.
- Headline VnExpress dùng **sans đậm**, deck **serif** — ngược với NYT.
- **4 font families** trên một trang (Montserrat, Georgia, Arial, Merriweather):
  có năng lượng nhưng thiếu kỷ luật — không copy; digest dùng 2 family.
- **Gotcha semantics:** desktop lead là `H4`, `H1` thật rỗng; mobile đổi body
  sang Arial. Không copy heading misuse hay font swap desktop/mobile.

### 2.3 Color & rules (CSS thật)

| Token | Hex | Bằng chứng |
|---|---|---|
| Brand crimson | `#9F224E` | **107 occurrences**; `.color_link_vne`, `.ic-vnexpress`, `.ic-comment`, `.live_news_status { background:#9f224e; }`, `.btn_send_email { background:#9f224e; }` |
| Meta grey | `#757575` | 30 occurrences |
| Hairline | `#E5E5E5` | 51 occurrences; `#box_most_read .tab_topstory_right { border-bottom-color:#e5e5e5; }` |
| Rail divider | `#F1F1F1` | `.item_most_read { border-bottom:1px solid #f1f1f1; padding-left:30px; }` |
| Warm block | `#F7F7F7` | 8 occurrences + mobile hero screenshot |
| Link blue | `#0B7CC1` / `#004F8B` | `a:hover`, `.color_link_default` |
| Live badge | `#9F224E` bg, white text | `.live_news_status { background:#9f224e; color:#fff; }` |

- **Một accent duy nhất** cho brand/active/live/comment; không tô màu section.
- Section header dùng gạch chân crimson ngắn 3px (đo từ screenshot).

### 2.4 Grid & modules

- **Đo ở 1440px:** `.container` rộng **1260px**, margin hai bên **90px**;
  lead column `.col-topnews` **640px**, story text **620px**, rail
  `.col_300_top` **300px** tại `x=1050`; nhịp dọc **20px**
  (`margin-bottom:20px`).
- Scale xuống 980px: ~**600px lead + 300px rail + 32px gutter** sau 24px page
  padding — khớp với grid 8/4 của digest.
- CSS có `grid-template-columns: repeat(2|3|4, 1fr)` cho các module khác nhau;
  top fold 50/26/24 là bố cục visual, không phải một rule duy nhất.
- **Most Read rail:** `#box_most_read`; tab active đậm + underline; item
  `border-bottom:1px solid #f1f1f1`, `padding-left:30px` (số thứ tự nằm trong
  30px gutter); số lớn màu `#BDBDBD` (đo từ screenshot).
- **Section fronts:** 2 cột 50/50; headline + deck + meta; hairline.
- **Nav:** ribbon đỏ đậm; trend/topic strip ngay dưới dateline.

### 2.5 Interaction / mobile

- Hover: headline underline / đổi màu; không animation phức tạp.
- Mobile: hero là block nền `#F7F7F7`, headline crimson; các story row gọn,
  hairline; nav/tab cuộn ngang.
- Không sticky mega-menu phức tạp trong popup 980px.

## 3. NYT — limited capture

- Screenshot `nytimes-desktop.png` là **trang block DataDome**; direct request
  trả 403 "You have been blocked... because we suspect that you're a robot"
  (ID `5a4f3526-68b9-31d8-b415-c37c0a206c74`). Không có pixel layout đáng tin.
- **Số đo CSS bên dưới lấy qua text proxy `https://r.jina.ai/https://www.nytimes.com/`**,
  không phải từ screenshot; dùng để tham khảo cấu trúc, không overclaim pixel.
- **Grid:** `grid-template-columns: repeat(14, 1fr)`; cell span 5/7/9/14 —
  đây là "broadsheet bones" đáng học: 12–14 cột + span 5/7.
- **Typography (CSS proxy):**
  - Cheltenham hero: `2rem/1.15 300 #121212`.
  - Card headline: `1.375rem/1.15 700`.
  - Imperial deck: `1rem/1.39 #5A5A5A`.
  - Franklin kicker: `0.6875rem/1.25 500`, uppercase, `letter-spacing:.1em`.
  - Meta: `0.625rem #727272`.
- **Palette:** `#121212` ink, `#5A5A5A` deck, `#727272` meta, `#EBEBEB` rule,
  accent `#346EB7` (blue link). Đây là palette NYT tham khảo, không phải palette
  digest (digest chọn crimson VnExpress).
- **Mobile NYT:** masthead blackletter căn giữa, date, subscribe pill, và
  full-screen offer modal — **không copy** paywall/modal.
- Các điểm NYT dùng trong plan (blackletter masthead, double rule, serif
  headlines, Most Popular, monochrome + blue link) là **public design language**
  + CSS proxy; không phải số đo từ screenshot live.

## 4. Comparison

| | NYT | VnExpress |
|---|---|---|
| Capture | Blocked (DataDome) | Real homepage |
| Headline | Serif, rất lớn, ít màu | Sans đậm 18–22, crimson cho lead mobile |
| Deck | Serif/sans nhỏ | **Georgia 14px #4F4F4F** |
| Grid | Nhiều cột + rail | Top 50/26/24; section 2 cột |
| Accent | Đen/trắng + blue link; đỏ breaking | **Crimson #9F224E** |
| Card | Không | Không |
| Rail | Most Popular | Most Read 1–5 |
| Motion | Gần như không | Gần như không |

## 5. Transfer to the 980px text-only digest

### Copy
1. **Asymmetric top fold** — hero 64% + rail 36% (briefing + Most Read), thay vì
   3 cột đều. VnExpress 1260 = 640 lead + 300 rail; scale 980 ≈ 600 + 300.
2. **Hairline rules** — 1px `#E5E5E5` / `#F1F1F1`; bỏ card/shadow/radius.
3. **Một crimson** `#9F224E` cho kicker/nav active/section underline; danger
   `.failed` dùng đỏ riêng `#B91C1C`.
4. **Numbered rail** — số lớn màu rule + headline 15–16px; "Nhìn lại" và
   "Đọc nhiều"; score/citations là small-caps meta token, không chip.
5. **Serif deck** — dùng Georgia/Cambria cho sapo (VnExpress 16/20.8; NYT
   Imperial 1rem/1.39); headline serif lớn (NYT bones) + sans meta.

### Don't copy
1. Hero image lớn / ảnh thumbnail (không có ảnh; text-first).
2. Nav ribbon đỏ full-width (quá nặng trong popup) và 90px outer margins /
   fixed 1260 canvas.
3. 3 cột đều hoặc cột <280px; ở 980px brief dùng 1 cột.
4. Bốn font families (Montserrat + Georgia + Arial + Merriweather) và font
   swap desktop/mobile; heading misuse (H4 lead, H1 rỗng).
5. Trending ticker khi chưa có structured topics; paywall/subscribe modal.

### Mapping
- `overview` → briefing box trong rail (3 numbered points).
- `ranked[0]` → hero 64%.
- `ranked[1:]` → section fronts (lead + briefs; 980px 1 cột brief).
- `pinned` → rail "Nhìn lại" (nếu có).
- `ranked[1:4]` → "Đọc nhiều" numbered links (không duplicate card).

## 6. Sources

- VnExpress homepage: https://e.vnexpress.net/ (200, 2026-11-19).
- VnExpress CSS: https://s.vnecdn.net/english/c/v367/en_general.css (2026-11-19).
- VnExpress font CSS: https://s.vnecdn.net/english/c/v367/fonts/Merriweather-woff2.css.
- Screenshots: `docs/research/news-ui/vnexpress-desktop.png`,
  `vnexpress-mobile.png`.
- NYT: https://www.nytimes.com/ — DataDome block page captured in
  `docs/research/news-ui/nytimes-desktop.png`; no homepage metrics.
