# Overview References — Implementation Plan

**Status:** approved direction, not implemented yet
**Baseline:** 351 tests pass (`uv run pytest -o addopts=''`)
**Feature:** "Trong ngày" overview references + click-to-article behavior

## 1. Goal

The daily overview must become clearer and more detailed about **all selected
items**, and every mention of an article must carry a clickable reference to
that article.

Clicking a reference:

- smooth-scrolls to the article card;
- highlights the card for ~2.5 seconds;
- focuses the card for keyboard/screen-reader users;
- updates the URL hash when the environment allows it.

Hard requirements:

1. Every selected item is referenced at least once.
2. If an item doesn't fit a theme point, a final `Còn lại hôm nay:` line lists
   its reference.
3. References appear **at the mention**, not as a chip list dumped at the end
   of the card.
4. Invalid/missing references never produce a broken link or a crash.
5. Legacy digests and plain-text overviews still render.
6. Every mode (LLM, heuristic, writer failure, `summarize=false`) still covers
   every item.
7. `digest_data` blob, feedback/ask bridge, print/PDF layout and the 09:00
   unattended run must not change.
8. No new runtime dependencies.

## 2. Decision

Use **inline markers in the existing overview string**:

- The writer keeps returning `{"overview": "...", "items": [...]}`.
- At each article mention, the writer writes `[[n]]` **in place of the article
  title**, where `n` is the 0-based candidate index the writer already sees:
  `[[0]]` is the first item, `[[1]]` the second, etc.
- The server parses the markers into inline reference chips.
- The server validates indices, drops invalid markers, deduplicates, and adds
  a `Còn lại hôm nay:` coverage point for any unreferenced item.
- A legacy overview without markers continues through the old rendering path.

### Why not structured points (`{"text": "...", "refs": [1,3]}`)

`top_n` is 12; 5 points × 1–2 refs caps coverage at 10. On a normal 12-item day
the writer cannot both obey the cap and cover everything, so the fallback
becomes a chip cluster at the card bottom — exactly what the user rejected.
Inline markers also satisfy "at the mention" more literally.

### Why not post-hoc title matching

Paraphrases, abbreviations and duplicate titles make matching unreliable, and
coverage cannot be guaranteed.

## 3. Data model and algorithms

### New module `daily_digest/overview.py`

```python
@dataclass(frozen=True)
class OverviewRef:
    uid: str
    label: str          # <= 28 chars, never a raw uid
    title: str          # full title for title="" / aria-label=""

@dataclass(frozen=True)
class OverviewSegment:
    text: str = ""
    ref: OverviewRef | None = None

@dataclass(frozen=True)
class OverviewPoint:
    segments: tuple[OverviewSegment, ...]
    kind: Literal["theme", "rest", "takeaway"] = "theme"


def parse_overview(
    text: str, ranked: Sequence[RankedItem]
) -> tuple[OverviewPoint, ...]:
    """Split text into points, replace valid [[n]] markers with refs."""

def ensure_coverage(
    points: Sequence[OverviewPoint], ranked: Sequence[RankedItem]
) -> tuple[OverviewPoint, ...]:
    """Append/replace a rest point so every ranked uid is referenced."""

def heuristic_overview_points(
    ranked: Sequence[RankedItem], config: Config
) -> tuple[OverviewPoint, ...]:
    """Deterministic fallback: one point per section, refs for every item."""

def short_label(title: str, number: int) -> str:
    """Title before ':', max 28 chars, word-boundary ellipsis, fallback 'Bài N'."""
```

### Marker grammar

- Regex: `r"\[\[(\d{1,3})\]\]"`.
- Index is **0-based** and must be a real `int` (reject `bool`, str, float).
- Out-of-range (`n < 0`, `n >= len(ranked)`) → drop marker, keep surrounding
  text.
- Dedupe repeated markers within the same point.
- Markers are not HTML; all text is autoescaped at render.

### Point splitting

- If the overview contains `\n\n`, split on blank lines.
- Otherwise split on sentence boundaries: `(?<=[.!?])\s+`.
- Preserve punctuation.
- Maximum 5 points: if more, keep the first 4 + the last (the takeaway).
- The last point is `kind="takeaway"`; it gets the `spotlight` style.

### Labels

```python
base = title.split(":", 1)[0].strip() or title.strip()
base = " ".join(base.split())
if len(base) > 28:
    cut = base[:28]
    cut = cut[:cut.rfind(" ")] if " " in cut else cut
    base = cut.rstrip(" ,;:.-") + "…"
return base or f"Bài {number}"
```

Full `title` is used in `title=""` and `aria-label`, never as visible text.

### Coverage

```python
covered = {
    seg.ref.uid
    for point in points
    for seg in point.segments
    if seg.ref is not None
}
missing = [item for item in ranked if item.item.id not in covered]
```

If `missing`:

- build a `kind="rest"` point:
  - first segment `Còn lại hôm nay: `
  - then each missing item as ` · ` + a ref segment;
- insert **before** the takeaway point (so the takeaway stays last);
- if there is no takeaway, append it.

If `points` is empty, build a rest point containing every ranked item.

Invariant: the union of all refs equals every ranked item's uid.

### Heuristic fallback

`heuristic_overview_points` groups ranked items by `SECTIONS`:

```text
Research Papers: [QDA] · [JET] · ...
Tech News: [Gemini] · ...
Tools & Releases: [vLLM 0.34] · ...
```

One point per non-empty section; every item gets a ref. This is the fallback
for writer failure, `summarize=false`, missing summary client, and heuristic
ranking. It is less polished than the writer overview but never leaves the
card without references.

## 4. File-by-file changes

### `daily_digest/overview.py` (new)
All dataclasses and functions from §3. No imports from `render` or `pipeline`
(avoid cycles). Allowed imports: `config`, `model`, `dataclasses`, `re`,
`typing`, `util.LOG` if needed.

### `daily_digest/ranking/llm.py`
- `SUMMARIZE_SYSTEM_PROMPT`:
  - 3–5 short points separated by blank lines.
  - At each mention, write `[[n]]` **in place of the title**.
  - Item list is 0-based; `[[0]]` is the first item.
  - Every numbered item must appear at least once.
  - Last point starts `Điểm cần nhớ:`.
  - No HTML, markdown links, URLs, or other bracket syntax.
  - Keep the existing JSON shape (`overview` string + `items`).
- `_validate_overview`:
  - Preserve `\n\n` (do not collapse all whitespace with `" ".join`).
  - Normalize spaces/tabs, collapse 3+ newlines to 2.
  - Cap `MAX_OVERVIEW_CHARS=1600` at a point/sentence boundary.
  - Remove an incomplete trailing marker (`[[`, `[[12`) before adding `…`.
  - Keep valid markers intact.
- `summarize_with_llm` signature stays `(ranked, overview_str)`.

### `daily_digest/pipeline.py`
After summaries:

```python
overview = ""
overview_points = ()
if config.llm.summarize and summary_client is not None:
    ranked, overview = summarize_with_llm(...)

if overview:
    overview_points = ensure_coverage(parse_overview(overview, ranked), ranked)

if not overview_points:
    overview = overview or heuristic_overview(ranked, config)
    overview_points = heuristic_overview_points(ranked, config)
```

Pass both to `render_digest`. The empty-digest early path stays unchanged.

### `daily_digest/render.py`
Add an optional argument:

```python
def render_digest(
    ...,
    overview: str = "",
    overview_points: Sequence[OverviewPoint] = (),
    ...
) -> str:
```

Forward `overview_points` to the template. `build_digest_data` is **not**
modified.

### `templates/partials/_story.html.j2`
- Add `tabindex="-1"` to story/pinned `<article>`.
- `rail()`:
  - If `overview_points`: render structured points:
    ```jinja
    <li class="overview-point{% if point.kind == 'takeaway' %} spotlight{% endif %}{% if point.kind == 'rest' %} overview-rest{% endif %}">
      <span class="overview-body">
        {% for seg in point.segments %}
          {{ seg.text }}{% if seg.ref %}<a class="oref"
            href="#story-{{ seg.ref.uid }}"
            data-story-ref="{{ seg.ref.uid }}"
            title="{{ seg.ref.title }}"
            aria-label="Chuyển đến bài: {{ seg.ref.title }}">{{ seg.ref.label }}</a>{% endif %}
        {% endfor %}
      </span>
    </li>
    ```
  - Else keep the **exact legacy branch**:
    ```jinja
    {% set points = overview.split(". ") %}
    {% set shown_points = points[:3] + points[-1:] if points | length > 3 else points %}
    ...
    ```
    This preserves old digests/tests.

### `templates/digest.html.j2`
- Add a delegated handler for `a[data-story-ref], a[href^="#story-"]`:
  - `getElementById(href.slice(1))`; if missing, let native behavior.
  - `preventDefault()`;
  - smooth `scrollIntoView` (auto under reduced motion);
  - `tabindex="-1"`, focus with `preventScroll`;
  - `.is-flash`, remove after 2500 ms (clear previous timer);
  - `history.replaceState` in `try/catch`;
  - optionally handle an initial `#story-` hash on load.
- Do not break existing section-nav smooth scroll or feedback/ask handlers.

### `templates/newsroom.css.j2`
- `.overview-body { flex: 1; min-width: 0; }`
- `.oref` inline chip:
  - accent color, subtle underline, font-weight 600, `text-underline-offset`.
- `.overview-rest` optional muted style.
- `[id^="story-"] { scroll-margin-top: 56px; }`
- `.story.is-flash` animation (outline/background); `.story:focus-visible` ring.
- Reduced motion: no smooth/flash animation; a static outline is acceptable.
- Print: hide `.oref` and `.overview-rest`; keep the text overview.
- Keep `.rail { align-content: start; }` so the card never stretches.

### Tests
- New `tests/test_overview.py` (parser/labels/coverage/heuristic).
- New `tests/test_overview_render.py` (chips/anchors/coverage/XSS/print).
- Update `tests/test_summarize.py` (markers/newlines/truncation).
- Update `tests/test_profile.py` (`GOLDEN_WRITER`).
- Update `tests/test_news_layout.py` / `test_ui_tokens.py` for `tabindex`,
  `.oref`, `.overview-body`, flash/reduced-motion/print rules.
- No tests should assert raw `[[n]]` remains in rendered HTML.

## 5. Implementation order (one commit per step)

### Step 1 — Interaction only
- `tabindex="-1"` on story articles.
- Delegated scroll/focus/flash handler for existing `#story-` anchors
  (most-read already uses them).
- CSS flash/focus/scroll-margin/reduced-motion.
- Tests: static selector/JS/CSS checks; manual click.
- No LLM change.

### Step 2 — `overview.py` + unit tests
- Dataclasses, parser, coverage, labels, heuristic points.
- Tests only; not wired.
- Suite green.

### Step 3 — Writer prompt + validation
- Prompt markers/coverage/takeaway.
- `_validate_overview` newline/marker preservation.
- Update golden writer test.
- Tests for markers/truncation/legacy.

### Step 4 — Pipeline + render + template
- Parse + coverage; optional `overview_points`; structured template branch.
- Legacy string branch untouched.
- Tests: anchors, coverage, XSS, `data-uid` counts.

### Step 5 — Fallback coverage
- `summarize=false`, no summary client, writer failure → heuristic points.
- Matrix test: every ranked uid has a chip in every mode.

### Step 6 — CSS/print/manual
- `.oref` inline style, `.overview-body`, flash, focus, print hide.
- Manual: browser + pywebview, light/dark, 980/1120/1600, keyboard,
  reduced motion, print page count, rail height.

## 6. Test matrix

### Unit
- Valid markers, labels, segment order.
- Invalid: `99`, `-1`, `"0"`, `True`, duplicate.
- Marker at start/end/punctuation; text remains clean.
- No markers → text-only point; legacy string.
- >5 points → first 4 + last.
- `short_label`: colon, long title, empty, max 28, no uid.
- Coverage: missing items → rest point before takeaway; union == all.
- Empty ranked → no crash.

### Render
- `href="#story-<uid>"`, `data-story-ref`, full `title`/`aria-label`.
- Visible label is short; no raw uid; no `[[` leak.
- Takeaway spotlight; rest class; legacy branch exact.
- XSS: `<script>`, quotes, `onerror` escaped.
- `data-uid` exactly once per story; chips have no `data-uid`.
- `tabindex="-1"` on article.
- Print CSS hides refs/rest.

### Pipeline
- LLM writer omits item 4 → rest line + chip for item 4; every ranked uid has
  at least one `href="#story-"`.
- Writer failure / no client / `summarize=false` → heuristic coverage.
- Malformed/empty overview → no crash, coverage still present.

### Static JS/CSS
- `a[data-story-ref]`, `getElementById`, `scrollIntoView`, `is-flash`,
  `2500`, `prefers-reduced-motion`, `scroll-margin-top:56px`, `try` around
  `replaceState`.

### Manual
- Click chip → scroll, flash 2.5s, focus.
- Keyboard Tab/Enter, focus-visible.
- Reduced motion: no smooth/flash.
- Hash best-effort; failure does not break scroll.
- Print page count; dark/light; three widths.

## 7. Verification commands

```bash
uv run pytest -o addopts='' tests/test_overview.py tests/test_overview_render.py
uv run pytest -o addopts=''          # full suite, >351
uv run daily-digest run --force
```

Artifact checks:

```bash
# No marker leaks
rg '\[\[' output/latest.html       # expect 0

# Every chip href resolves to exactly one story id
# Count distinct refs / coverage with a small Python check
uv run daily-digest open --web latest
```

Manual: click references in the popup, Tab/Enter, reduced motion, print.

## 8. Risks and rollback

| Risk | Mitigation |
|---|---|
| LLM uses 1-based indices | Prompt explicitly says 0-based + example; live-check chip labels against titles |
| LLM omits markers | Coverage adds `Còn lại hôm nay:` refs |
| Marker leaks (`[[3]]`) | Tolerant parser removes invalid; test `rg '\[\['` |
| Coverage line becomes a chip dump | Prompt asks inline markers for every item; rest is fallback only |
| Overview too tall | 3–5 points, inline chips, 1600 cap; screenshot 980/1120/1600 |
| Print layout changes | Hide `.oref`/`.overview-rest` in print |
| Rail stretches | Keep `align-content:start`; `.overview-body` wrapper |
| Hash unsupported in pywebview | Scroll/flash does not depend on hash; hash best-effort |
| Rollback | Remove prompt markers + `overview_points`; legacy string branch remains; `digest_data` untouched |

## 9. Defaults / open decisions

1. Marker **replaces** the title at the mention, avoiding `QDA [QDA]`.
2. Chip label = short title; full title in `title`/`aria-label`.
3. Print hides refs/rest; print text stays as before.
4. Hash is best-effort; click scroll/flash is the acceptance behavior.
5. No Playwright dependency; static JS/CSS tests + manual verification.
6. Every mode must cover every item; heuristic uses section groups.
7. No change to `top_n`, blob, bridge, print, or 09:00 run.

## 10. Definition of done

- 6 commits, each with the suite green.
- Full suite >351, all green.
- `run --force` exit 0.
- `latest.html` contains no `[[`, every chip `href` resolves, every ranked uid
  has at least one chip.
- Click smooth-scrolls, flashes 2.5s, focuses the card; keyboard works;
  reduced-motion respected.
- Legacy digests without markers still render.
- Print hides references without changing layout/page count.
- No new dependencies; `digest_data`, bridge, print and 09:00 path unchanged.
- Final report includes command output, live artifact checks, and manual
  click/print evidence.
