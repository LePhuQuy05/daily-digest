# UI Redesign Plan — "Editorial Dark Reading Room"

*Kế hoạch làm đẹp digest popup, tổng hợp từ: ui-ux-pro-max (design-system search
"AI research digest reader" → style **AI-Native UI**; typography "editorial
reading" → **Newsreader/Magazine** pairings; color "dark reading dashboard" →
calm-slate palettes; style "minimal editorial" → **Swiss minimalism**) +
design-system skill (token 3 lớp) + phân tích constraint của chính template.*

## 1. Vấn đề được phát biểu lại (Reformulation)

Digest popup hiện tại là "một trang web nhạt đặt trong cửa sổ". Phát biểu lại:
**đây là "tờ báo AI buổi sáng" của riêng bạn** — trải nghiệm 3 nhịp:
**lướt** (overview) → **quét** (sections, titles, why-lines) → **đọc/hành động**
(summaries, 👍/🔖/Hỏi). Mọi quyết định UI phục vụ 3 nhịp đó, theo thứ tự ưu tiên.

Two-sentence test: *"Digest readers strain the eyes because generic light web
cards fight the desktop and bury signal in uniform text. We build an editorial
dark reading surface with newspaper serif titles, semantic section colors, and
glance→skim→read hierarchy — which works because contrast, spacing rhythm and
type pairing are exactly what a 2-minute daily read needs."*

## 2. Ràng buộc (phân tích constraint — F4)

**Hard (không vi phạm):**
- Một file Jinja2 duy nhất (`templates/digest.html.j2`) — không build system, không npm, inline CSS/JS
- Offline-first: **không CDN fonts** (popup có thể mở khi mất mạng) → font stack hệ thống; `@font-face` chỉ trỏ vào `assets/fonts/*.woff2` bundle (optional enhancement)
- WebView2 = Chromium hiện đại: OK dùng `color-mix()`, `:has()`, `backdrop-filter`, CSS grid, `prefers-reduced-motion`
- Cùng template phục vụ popup (bridge) và browser `--web` (không bridge) — `.bridge-only` mechanics + data blob phải sống nguyên
- Class names đang bị test khóa (`.bridge-only`, `.summary.ai`, `pinned-block`, `digest-data` script tag...) — giữ tên, đổi skin
- Contrast ≥ 4.5:1 cho text; focus rings hiển thị; respect `prefers-reduced-motion`

**Soft/Hidden bị thả bỏ:**
- "Light theme mặc định" → dark-first (reading app buổi sáng trên desktop, cảm giác native app; light mode vẫn có qua toggle)
- "Font hệ thống cho tất cả" → **serif hệ thống cho tiêu đề** (Georgia/Segoe UI Variable Serif — editorial "morning paper") + sans hệ thống cho UI — zero dependency
- "Emoji làm icon" (👍👎🔖📌) → **inline SVG stroke icons** (Lucide-style) — checklist của skill cấm emoji-as-icons
- "3 cột phẳng như nhau" → 3 cột có màu nhận diện section (giữ semantic colors hiện có: papers teal / news amber / tools emerald) + rhythm rõ

## 3. Hướng thiết kế (từ search + tổng hợp)

**Style**: AI-Native UI × Swiss minimalism × News-editorial typography.
- **Dark-first, calm slate**: bg `#0B1220`-deep, card nâng nhẹ, border tinh tế (theo palette "dark reading dashboard" — Financial Dashboard dark + điều chỉnh)
- **Accent violet** `#8B5CF6` (họ hàng indigo hiện tại #6366f1, tinh chỉnh theo AI-Native #7C3AED) + **cyan** cho link/hành động (`#22D3EE`) — "AI purple + cyan interactions"
- **Section identity**: papers `#2DD4BF` (teal) / tech_news `#F59E0B` (amber) / tools `#34D399` (emerald) — thanh màu 3px bên trái card + số section
- **Typography**: tiêu đề serif (Georgia, `Segoe UI Variable Serif`) 600-700, tracking nhẹ; UI sans (`Segoe UI Variable Text`, fallback system). Cỡ: 13px meta / 14.5 why / 15.5 summary / 18-19 title / 28-30 H1. Overview card theo nhịp **AI briefing**: gradient accent nhẹ, top-line shimmer, bullet quét nhanh + spotlight cho câu chốt; **không drop-cap** (drop-cap cắt đôi chữ tiếng Việt và tạo cảm giác báo giấy)
- **Effects (AI-Native)**: typing-dots cho "Đang nghĩ…" (3 chấm pulse), reveal stagger cards khi load (rise từ opacity 0.55 — không bao giờ vô hình, 30ms/stagger, cap 4 card, tắt khi reduced-motion), hover card lift 2px + glow section-color
- **Tránh** (từ AVOID của search): heavy chrome, phản hồi chậm, gradient lòe loẹt, glassmorphism cường điệu

## 4. Token architecture (design-system 3 lớp, đặt trong `:root` + `[data-theme]`)

```
PRIMITIVE   --slate-950..200, --violet-400..600, --cyan-400, --teal-400, --amber-400, --emerald-400
SEMANTIC    --bg, --bg-raised(card), --text-1/2/3, --accent, --accent-soft, --link, --border,
            --section-papers/news/tools, --danger, --ring
COMPONENT   --card-radius 14px, --card-gap 14px, --card-hover-shadow, --btn-*, --chip-*,
            --focus-ring: 2px --ring offset 2px
```
Light theme = override semantic layer bằng `[data-theme="light"]`; mặc định theo
`prefers-color-scheme`, user toggle (nút 🌓 → SVG moon/sun) lưu `localStorage` —
JS 5 dòng, hoạt động cả trong browser.

## 5. Component specs (giữ class names hiện tại)

| Component | Spec mới |
|---|---|
| Header | Sticky, blur backdrop nhẹ, ngày + badge mode (viền accent), counts chips; H1 serif |
| Overview card | Viền-trái accent 4px + gradient accent nhẹ, top-line shimmer (tắt khi reduced-motion), label "TỔNG HỢP HÔM NAY · TL;DR" violet + sparkle SVG; nội dung bullet hóa (tối đa 4 câu), câu chốt là spotlight box với mũi tên →, **không drop-cap** |
| Section header | Số thứ tự serif lớn mờ + tên + count pill màu section |
| Item card | Radius 14, border `--border`, hover: translateY(-2px) + shadow + left-bar màu section sáng dần; title serif 18px; meta chips (source, pts, citations) dạng pill nhỏ; why-line màu accent-2 có icon ↗ nhỏ (SVG); summary `.summary.ai` có label "SUMMARY" như hiện tại |
| Feedback buttons | Icon-only SVG 18px trong pill 32×32, `cursor-pointer`, tooltip title giữ; state `.done` = nền accent + icon trắng, `.failed` = viền đỏ; transition 180ms |
| Ask drawer | Input + nút "Hỏi" đồng bộ token; answer box nền muted, "Đang nghĩ…" = 3 dot pulse animation; fade-in 200ms |
| Pinned "Nhìn lại" | Card viền dashed amber nhẹ + icon pin SVG; nút "✓ Đọc xong" giữ |
| Banners | degraded/notice: đỏ/camber nhạt như hiện tại, thêm icon SVG |
| Footer | Mờ, nhỏ, mono-ish (ui-monospace) |
| Print | `@media print`: light, ẩn bridge-only/footer, cột thành 1 — lưu PDF đẹp |

## 6. Icon set (inline SVG, 7 icons, stroke 1.75, 18px)

thumbs-up, thumbs-down, bookmark, bookmark-filled (done), pin, check, send/arrow,
moon/sun (theme toggle), external-link (title hover). Tất cả inline trong template
(dùng `<svg><use>` với `<defs>` một lần) — không file ngoài, không emoji.

## 7. Lộ trình triển khai (mỗi bước shippable, suite xanh)

1. **Token layer + dark default**: thêm `:root` tokens + `[data-theme]` + toggle JS; đổi mọi raw hex hiện tại sang `var(--*)` (chỉ trong `<style>` của template). Cập nhật test CSS-string assertions. *Proof: popup dark, light toggle hoạt động.*
2. **Typography + header + overview**: serif titles, scale mới, sticky header, overview AI-briefing (gradient + shimmer + bullets + spotlight arrow, không drop-cap). *Proof: hierarchy thấy rõ.*
3. **Cards + sections + chips**: section identity bars, meta pills, hover states, stagger reveal (reduced-motion-safe). *Proof: 3 nhịp lướt→quét→ đọc.*
4. **Icons thay emoji + button/drawer states**: SVG defs + thay 4 nút + pin/check + theme toggle + typing-dots. *Proof: không còn emoji-as-icon; states rõ.*
5. **Print CSS + polish**: @media print, focus-visible audit, contrast audit (4.5:1 từng cặp token), empty states đẹp. *Proof: checklist pre-delivery pass.*

## 8. Verification

- **Tự động (pytest, cập nhật assertions hiện có)**: tokens có đủ biến semantic; không còn raw hex ngoài primitive layer; `.bridge-only`/`pinned-block`/`.summary.ai`/blob tag giữ nguyên; `prefers-reduced-motion` có media query; mọi nút có `cursor:pointer` + focus-visible; không emoji 👍👎🔖📌 trong template (grep).
- **Contrast**: tính tỷ lệ từng cặp (text/bg, muted/bg, accent/bg) ≥ 4.5:1 — script nhỏ hoặc bảng tay ghi vào PR.
- **Overview**: không còn `::first-letter`/drop-cap; bullet list + spotlight arrow; shimmer tắt dưới `prefers-reduced-motion`; overview truncation cắt theo word-boundary + "…" (test riêng).
- **Manual smoke**: popup thật — dark/light toggle, hover cards, 👍 (đổi state), Hỏi (dots → answer), pinned card, resize hẹp (980px popup min) không vỡ, `open --web` không lộ bridge UI, in 1 trang PDF.
- **Pre-delivery checklist** (từ ui-ux-pro-max): contrast / keyboard / focus / reduced-motion / responsive 375–1440 / hover 150–300ms / cursor-pointer / SVG icons.

## 9. Revision log

- **2026-11-19 — overview card**: user feedback "đừng cái mục tổng hợp hôm nay
  đứng yên như vậy, khó coi". Đã bỏ drop-cap hoàn toàn (nó cắt đôi chữ "Hôm"),
  chuyển overview sang AI-briefing: gradient surface + shimmer top-line
  (reduced-motion-safe), bullet tối đa 4 câu, câu chốt trong spotlight box với
  mũi tên →. Kèm theo: reveal không bắt đầu từ opacity 0; `.done` là fill accent
  solid; ask input + nút "Hỏi" cùng một hàng; degraded banner thu thành pill.

## 10. Out of scope (ghi rõ để không scope-creep)

Frameless window + custom titlebar (pywebview `frameless`), animation GSAP, web
fonts bundle (chỉ đặt sẵn `@font-face` hook), search/filter trong popup, chart
topic-trend — các mục này thuộc roadmap Tier 2/3 (docs/feature-roadmap.md).
