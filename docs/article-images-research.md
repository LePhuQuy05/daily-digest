# Article images for the daily digest — feasibility & design

> **Researched:** 2026-11-19 on the current 12-item digest (11 arXiv + 1 HN).
> **Scope:** every future daily digest, not a one-off. Attach a **real article
> figure/OG image when one exists**, cached and embedded offline.
> **POC contact sheets:** `output/image-research/final-contact-sheet.png`
> (11 arXiv figures + 1 HN OG) and `output/image-research/poc-contact-sheet.png`
> (includes rejected HF/GitHub candidates).

## 0. TL;DR

**Có cách, và coverage rất tốt — nhưng phải source-aware.**
Naive OG trên arXiv chỉ trả **logo arXiv**, không phải ảnh bài báo. Cách đúng:

1. **arXiv HTML**: lấy `<figure class="ltx_figure">` đầu tiên.
   - Nếu là `<img>` → tải ảnh.
   - Nếu là **inline SVG** → rasterize bằng headless Edge (giữ đúng figure).
   - Bỏ `<figure class="ltx_table">`, logo, spacer.
2. **HN**: target URL qua **Algolia API** (`hn.algolia.com/api/v1/items/<id>`)
   → OG/Twitter image của bài gốc.
3. **Tools/GitHub**: chỉ dùng **social preview do user upload**
   (`repository-images.githubusercontent.com`); **không** dùng banner auto
   `opengraph.githubassets.com` (chỉ là text).
4. **Bài blog/news khác**: OG/Twitter image; bỏ logo/favicon/placeholder.
5. **arXiv PDF**: fallback optional, chỉ khi HTML không có figure; chỉ trích
   được raster (nhiều paper vector-only nên không đủ).
6. **Không có ảnh** → không có slot ảnh; text-first vẫn đẹp. Không dùng ảnh giả.

**Kết quả thực tế hôm nay: 11/11 paper arXiv có figure thật** (4 `<img>` +
7 inline SVG rasterized; **10/11 usable** — `22171` là text table nhỏ, skip),
cộng 1 OG bài HN mẫu. Item HN hiện tại là self-post không có target URL nên
không ảnh. **Không dùng LLM để sinh ảnh** — vừa không phải ảnh bài báo, vừa làm
mất credibility của một technical broadsheet.

## 1. Empirical findings

| Item | arXiv HTML figure | Kind | Visual QA |
|---|---|---|---|
| 2611.16069 | `arbitrary_trigger.png` | img | ✅ real Fig. 1 (plot + transcript) |
| 2611.20003 | inline SVG | SVG | ✅ real figure |
| 2611.21003 | `k2_horizon_lead_compact.png` | img | ✅ Fig. 1 benchmark grid |
| 2611.21152 | inline SVG | SVG | ✅ real figure |
| 2611.21705 | inline SVG | SVG | ✅ real figure |
| 2611.21766 | inline SVG | SVG | ✅ real figure |
| 2611.21791 | `kl_role_agentic.png` | img | ✅ Fig. 1 architecture + curves |
| 2611.22171 | inline SVG | SVG | ⚠️ weak (tiny text table) — skip |
| 2611.22234 | inline SVG | SVG | ✅ real figure |
| 2611.22238 | inline SVG | SVG | ✅ real figure |
| 2611.22539 | `overexploration_case.png` | img | ✅ Fig. 1 portrait diagram |
| HN self-post | — | — | no target URL → no image |

- **Naive OG on arXiv:** all abs pages return
  `/static/browse/0.3.4/images/arxiv-logo-fb.png`; **never use it as the story
  image.**
- **arXiv HTML figure URL:** relative to `https://arxiv.org/html/` — e.g.
  `2611.16069v2/arbitrary_trigger.png`. Do **not** join to
  `/html/<id>/` (404).
- **Inline SVG figures:** arXiv HTML now renders many figures as inline SVG.
  Extract the first `<figure class="ltx_figure">` (skip `ltx_table`), wrap with
  the page's `<style>` blocks + `<base href="https://arxiv.org/html/<id>">`,
  **hide `<figcaption>`/`.ltx_caption`**, screenshot the `<svg>` at ~1200px,
  and auto-trim whitespace. Do **not** capture the full-width figure element:
  the caption spans the page and shrinks the actual chart into the corner.
  This took coverage from 4/11 to **11/11**; `22171` is a tiny monochrome text
  table and should be skipped.
- **HF `thumbnail` = page-1 text crop** (`cdn-thumbnails.huggingface.co/
  social-thumbnails/papers/<id>.png`). Vision verdict: looks like a screenshot
  of the title/abstract, blurry, cheap; **reject**. It is not a figure.
- **GitHub auto OG** (`opengraph.githubassets.com`) is a text banner with repo
  name/description/stars; **reject**; only user-uploaded social preview.
- **HN page** returns 419 to urllib; use **Algolia API**. Current Launch HN
  self-post has `url: null`; normal HN stories have a target URL (Wiz blog OG
  sample: 760×423, real editorial hero).
- **PDF fallback:** `2611.21152` has a raster figure; `2611.20003` and the five
  SVG-only papers have **vector-only** figures — PyMuPDF `get_images()` finds
  nothing. PDF raster is a partial fallback, not the primary.
- **LLM provider:** chat-only OpenAI-compatible (`opencode.ai/inference/go`);
  `tools.opencode.models(type=image)` returns 0 image models. AI image
  generation needs a separate provider/local model — not v1.

## 2. Options

### A. Naive OG for every item — REJECT
One `og:image` per URL. arXiv returns the arXiv logo; many tools return
logos/placeholder. Visually misleading and repetitive.

### B. Source-aware real figures + article OG — RECOMMENDED
- arXiv HTML first `ltx_figure` (img or inline SVG rasterized).
- HN target OG via Algolia; generic article OG; GitHub user social preview.
- arXiv PDF raster only as a last resort.
- Cache + resize + data URI; only selected 12 items; failures never block.
- **Pros:** real, free (httpx/Pillow already; Edge already used for print),
  11/11 current arXiv coverage, no fake images.
- **Cons:** Edge rasterization adds ~1–2s/figure; some figures are dense;
  HN self-posts/no-OG remain text-only.

### C. LLM-generated illustration for every item — REJECT as default
- 100% coverage but not the article's image; credibility risk for technical
  readers; cost/latency; no image model in current provider.
- Optional only if the user explicitly wants labelled **"AI illustration"**
  fallback for no-image items; not the default.

### D. Hybrid: B + clean text fallback
- No-image items keep the existing typography/section stamp; the page still
  looks like a broadsheet. This is the default.

## 3. Recommended architecture (future daily runs)

### 3.1 New module `daily_digest/media.py`

```python
@dataclass(frozen=True)
class ImageAsset:
    uid: str
    data_uri: str
    alt: str
    credit: str            # "Hình: arXiv:2611.16069" / "Ảnh: Wiz"
    source_url: str
    kind: str              # "arxiv_img" | "arxiv_svg" | "article_og" | "github_social" | "pdf"
    width: int
    height: int

def collect_images(ranked: Sequence[RankedItem], config) -> dict[str, ImageAsset]:
    """Best-effort, cached, concurrent; never raises into the pipeline."""
```

Resolver priority:
1. **arXiv** (`arxiv.org/abs/<id>`):
   - fetch `https://arxiv.org/html/<id>`;
   - first `<figure class="ltx_figure">` (skip `ltx_table`);
   - `<img>` child → download; else inline `<svg>` → rasterize via Edge.
   - no figure → optional PDF raster fallback.
2. **HN** (`news.ycombinator.com/item?id=...`):
   - Algolia item → `url`; if null, parse `text` for first external link;
   - GitHub URL → user social preview; else generic article OG.
3. **Other sources / tools**: GitHub user social preview; generic OG.
4. **No image**: no slot.

### 3.2 Fetch / process

- `httpx.Client` (existing dependency), browser UA, timeout 8s, max 5MB,
  follow redirects, only http/https.
- Validate: raster content type (jpeg/png/webp), max pixels, no SVG download;
  skip logo/icon/spacer (`arxiv-logo`, `icon`, `badge`, `data:`).
- **Rasterize inline SVG** via Edge:
  - extract the figure HTML + page `<style>` blocks; strip `<script>` and
    `on*=` attributes; add `<base href="https://arxiv.org/html/<id>">`;
  - **hide `figcaption`/`.ltx_caption`**, force the SVG to ~1200px, screenshot
    with a unique `--user-data-dir`, then auto-trim whitespace to the SVG bbox;
  - skip if the trimmed image is a tiny monochrome text table (e.g. `22171`).
- **Contain, not cover** for figures: crop axes/legends is unacceptable.
  - light: 16:10 warm mat `#F4F1EA`, border `--rule`, padding 10–14px;
    `mix-blend-mode: multiply` to blend white chart backgrounds.
  - dark: mat `#E6E3DC`, `filter: brightness(0.93)`; never `invert(1)`.
  - OG photos: 16:9 cover is fine.
- Resize max 1180px wide (figures) / 960px (OG); JPEG q82/88; cache.
- Cache `output/media/<sha1>.<jpg>` + manifest; prune > 30 days.
- Data URI embedded in HTML; HTML budget ~1.2MB; drop lowest priority.

### 3.3 Pipeline / config

- After ranked + summaries + pinned, before `render_digest`:
  `images = collect_images(ranked, config)`.
- Pass `images` as an **additive optional** param to `render_digest` (existing
  callers unaffected); `digest_data` blob unchanged.
- Config:
  ```yaml
  media:
    enabled: true
    max_images: 6            # hero + section leads only
    timeout_seconds: 8
    max_bytes: 5000000
    width: 1180
    include_in_print: true
    ai_fallback: false       # optional, not v1
  ```
- Only selected items; 2–4 workers; per-item failures logged; digest always
  renders.

### 3.4 Template / layout

- Add an optional media block to `_story.html.j2` for:
  - **hero** and **section leads** (papers/news/tools);
  - **not** the secondary lead by default: two full-width 16:9 mats stacked in
    the top fold overpower the layout and outrun the rail. Secondary stays
    text-only; an optional 120px side-thumb is a later polish.
  - **Not** briefs/more/rail: charts become illegible at 240–285px.
- `figure.story-media`:
  - figures: `object-fit: contain` on a 16:10/16:9 warm mat, caption/credit below.
  - OG photos: 16:9 `cover`.
  - light mat `#F4F1EA` + `mix-blend-mode: multiply`.
  - night mat `#EAE6DD` + `filter: brightness(0.92)`; **do not** invert. Match
    the mat to the dimmed figure white point to avoid letterbox seams.
- No image → no slot; no placeholder fake image.
- Column rules (`briefs`, rail) carry **18px padding** so text never touches the
  vertical rule; portrait figures use a **3:4 mat** (hero capped at 460px), not a
  letterboxed 16:9 strip.
- Print: include hero/section-lead images at small size; test A4 page count;
  config can disable.
- Alt text: figure `<figcaption>` / article title; credit `"Hình: arXiv:<id>"` /
  `"Ảnh: <host>"`.

## 4. Security / legal

- **SSRF:** http/https only; reject loopback/private/link-local IPs; cap
  redirects.
- **Image safety:** max bytes/pixels, raster only, no raw SVG in the final HTML;
  Jinja autoescape alt/credit; cache filenames sha1.
- **Edge rasterization:** strip scripts/event handlers from the extracted
  figure; unique profile; local wrapper; no page JS.
- **Copyright:** figures/OG are source content; personal digest, cache locally,
  attribute source, do not redistribute; respect robots/ToS.
- **Privacy:** no auth, no image upload to an LLM by default; AI fallback
  opt-in only.

## 5. Tests

- `tests/test_media.py`:
  - arXiv HTML: first `ltx_figure`; skip `ltx_table`; `<img>` URL resolution;
    inline SVG detected; no figure → fallback.
  - OG parser: `og:image`/`twitter:image`; reject arXiv logo, HF social,
    GitHub auto banner, tiny/placeholder.
  - HN Algolia target; GitHub user social preview.
  - Cache hit/miss; contain/cover; data URI; max bytes/pixels; timeout.
  - SSRF/private IP block; non-image content; Edge unavailable fallback.
  - `collect_images` never raises; partial coverage.
- `tests/test_render_images.py`:
  - With image: `<figure>`, data URI, alt/credit; no external `http` in head;
    only hero/lead variants have media; briefs never.
  - Without image: identical to current text layout.
  - Print include/omit.
- Existing 260-test suite stays green; render signature additive.

## 6. Phases

1. **P1 — arXiv figures + cache + layout**:
   HTML `<img>` + inline SVG Edge rasterizer; cache/data URI; images on **hero
   and section leads** (secondary text-only); tests. *Shippable.*
2. **P2 — HN / generic article OG + GitHub user preview**:
   Algolia target; OG filters; Tech News images; tests.
3. **P3 — PDF raster fallback** (optional; PyMuPDF ~60MB) for arXiv without
   HTML figure; measure coverage; may skip.
4. **P4 — optional caption/alt via LLM** (not image generation); print/vision
   QA; config polish.

## 7. Open questions

- Images only hero + section leads (recommended, per vision); **secondary stays
  text-only** by default (two full-width mats overpower the top fold). Briefs
  text-only; charts at 240–285px are illegible.
- Edge rasterization cost (~1–2s/figure) is acceptable once/day; if Edge is
  missing, fall back to no image.
- PDF fallback worth the 60MB PyMuPDF dependency? Current HTML coverage 11/11
  makes it low priority.
- AI illustration only if the user explicitly opts in and labels it; not
  default. Current provider has no image model.
- Print: include figures or keep text-only? Test page count.

## 8. POC artifacts

- `output/image-research/final-contact-sheet.png` — 11 arXiv figures + HN OG
  (tight-cropped SVG after hiding captions).
- `output/image-research/poc-contact-sheet.png` — includes rejected HF/GitHub
  candidates.
- `output/newsroom-with-images-final.html` +
  `newsroom-with-images-final-1120.png` / `-dark-1120.png` — **final layout
  mockup**: hero + section lead images only; secondary text-only; dark mat
  #EAE6DD.
- `output/newsroom-with-images.html` + `newsroom-with-images-1120.png` /
  `-dark-1120.png` — earlier stress-test mockup with hero + secondary + lead
  (kept to show why two full-width mats are too much).
- `output/image-research/*.jpg` — downloaded/rasterized candidates.
- Vision verdict: arXiv figures = genuine/legible; HF page-1 thumbnails and
  GitHub auto banners = reject; no LLM images; images only hero + section leads
  (secondary text-only); skip tiny text-table figures (e.g. 22171).
- **Final layout sign-off:** **ship** — hero + section leads, secondary text-only,
  dark mat `#EAE6DD`; the 4:3 letterbox is now a tasteful paper border.

## 9. Phase 1 implemented (2026-11-19)

- **App model:** default changed to `deepseek-v4.1-flash` (OpenCode Go); the
  same vision-capable model now reviews image suitability.
- **Code:** `daily_digest/media.py` (arXiv `<img>`, inline `<svg>`, `<object>`
  SVG files, HN Algolia/OG, generic OG, cache, data URI, LLM review);
  `pipeline.py` collects images after summaries; `render_digest(images=...)`
  additive; `_story.html.j2` renders media only for hero/lead.
- **Tests:** `uv run pytest` → **273 passed**.
- **Live run (`run --force`, DeepSeek):** media **2/3 slots filled**:
  - hero `arxiv:2611.15671` → first inline SVG figure;
  - section lead `arxiv:2611.22238` → figure;
  - third target (Tech News OG) **rejected by DeepSeek**:
    *“Generic AI chip stock image; not specific to the audit trial and adds
    little informational value.”* → no image, exactly the intended filter.
- **Shipped artifact:** `output/latest.html` (302,333 bytes, 2 data-URI figures);
  screenshots `output/newsroom-final-light-1120.png` /
  `newsroom-final-dark-1120.png`; `open --web` exit 0.
- **Explicitly rejected:** HF page-1 social thumbnails, auto GitHub banners,
  LLM-generated images, images in brief columns.
