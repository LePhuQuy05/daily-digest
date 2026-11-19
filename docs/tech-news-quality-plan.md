# Tech News Quality & Source Health — Implementation Plan

**Date:** 2026-11-19
**Status:** approved direction (architect + critic review), not yet implemented
**Sprint goal:** fix the two structural quality problems the latest digests exposed,
without touching the archive/digest contracts.

## 1. Why this sprint (evidence)

- `sources/hn.py` fills `summary` only from Algolia `story_text`, which is empty
  for link posts. Selected HN items then render as
  *"No description provided; from the title…"* (KPMG audit trial, prompt
  inversion). Empty summaries also weaken `balanced_pool`, which scores HN
  relevance from `title + summary`.
- The 2026-11-19 digest picked **two Hugging Face posts** for Tech News. A
  per-source cap with a qualified fallback gives the editor-visible diversity
  the reader asked for, without padding thin items.
- The `feeds` source now owns **20 feeds**, but a partial feed failure is only
  a log line. There is no way to ask "which feed is dead today?" without
  reading `logs/daily-digest.log`.
- Deliberately **not** in this sprint: archive index/search (only 1 indexable
  day; `digest-2026-11-18.html` has no `digest-data` blob), MCP, audio,
  weekly recap, trend chips. Revisit archive when there are **≥10 blob days**
  or the owner actually searches.

## 2. Scope

### In scope
1. Shared, SSRF-safe article fetch + description extraction (refactor of code
   that already exists in `sources/feeds.py` and `media.py`).
2. HN link-post hydration before ranking (bounded, best-effort).
3. Tech News source-diversity guard (max 1 per source **when a qualified
   replacement exists**).
4. `daily-digest health` — per-feed status command.
5. Docs/config/README updates and live verification.

### Must not change
- `digest_data` JSON blob shape, feedback/ask bridge, popup bridge contract.
- Print/PDF layout, templates, CSS (no UI change in this sprint).
- `run_day` exit-code semantics: new steps are best-effort and never degrade.
- Heuristic fallback behavior for papers/tools sections.

## 3. Architecture after the sprint

```
fetch_all (unchanged)
   │
merge → seen → mute                       (unchanged)
   │
HN hydration          ← NEW: article.hydrate_hn_links(fresh, config)
   │                     bounded (≤12 pages), AI-title filter, best-effort
balanced_pool         (unchanged; now sees real HN summaries)
   │
enrich_citations      (unchanged)
   │
select                ← NEW: diversify_tech_news(ranked, pool, config)
   │                     before top_n slicing; tech_news only
summarize → media → render → notify       (unchanged)
```

`daily-digest health` is a standalone CLI path (no pipeline integration):

```
cli.cmd_health → feeds.check_feeds(client, config.sources.feeds) → table
```

## 4. Step 1 — shared safe fetch + article helpers (refactor, no behavior change)

### Files
- **New** `daily_digest/net.py`
- **New** `daily_digest/article.py`
- **Modify** `daily_digest/media.py` (import instead of duplicating)
- **Modify** `daily_digest/sources/feeds.py` (import instead of duplicating)

### `daily_digest/net.py`
Move the SSRF/redirect logic that already exists in `media.py`
(`_assert_public_url`, `_get`) and make it reusable:

```python
def assert_public_url(url: str) -> None:
    """http(s) only; reject localhost/.local and non-global IPs."""

def host_is_public(host: str) -> bool:
    """Separated so tests can monkeypatch DNS resolution."""

def get_public(
    client: httpx.Client,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
    max_redirects: int = 4,
) -> httpx.Response:
    """Follow redirects manually, validating every hop (SSRF-safe)."""
```

`media.py` keeps thin aliases (`_assert_public_url = assert_public_url`,
`_get = get_public`) so `tests/test_media.py` imports keep working; call sites
move to `net.get_public`.

### `daily_digest/article.py`
Move the description helpers out of `sources/feeds.py`
(`_clean_html`, `_meta_description`, `_article_lead`, `_hydrate`) so both the
feeds source and the new HN hydration use one implementation:

```python
MAX_ARTICLE_BYTES = 2_000_000
MIN_DESCRIPTION_CHARS = 80
MAX_SUMMARY_CHARS = 1500
ARTICLE_TIMEOUT = 8.0
ARTICLE_USER_AGENT = "Mozilla/5.0 (compatible; DailyDigest/1.0)"

def clean_html(value: str) -> str: ...
def meta_description(page: str) -> str: ...
def article_lead(page: str) -> str: ...

def hydrate_item(
    client: httpx.Client,
    item: Item,
    *,
    timeout: float = ARTICLE_TIMEOUT,
    max_bytes: int = MAX_ARTICLE_BYTES,
    min_chars: int = MIN_DESCRIPTION_CHARS,
) -> Item:
    """Fetch the item's page (SSRF-safe) and fill a thin summary.

    Order: og/twitter/plain meta description → first substantive paragraph.
    Best-effort: blocked/slow/oversized pages return the item unchanged.
    """
```

`hydrate_item` must use `net.get_public` (not a bare `client.get`) because HN
link targets are untrusted URLs; redirects must be validated per hop.

`feeds.py` drops its private copies and imports
`clean_html`, `hydrate_item` (and the constants it still needs) from
`article.py`. `parse_feed` behavior is unchanged.

### Tests (move/extend, no behavior change)
- Move the `_article_lead` / hydration tests from `tests/test_feeds.py` to a
  new `tests/test_article.py`; keep the `fetch_feeds` hydration integration
  test in `test_feeds.py`.
- `tests/test_article.py`:
  - `meta_description` picks the longest useful description.
  - `article_lead` skips nav paragraphs, picks the intro.
  - `hydrate_item` fills a thin summary from `og:description`.
  - `hydrate_item` keeps the item unchanged on HTTP error / timeout / oversized
    page / description shorter than `min_chars`.
  - SSRF: private/non-http URLs are rejected (`net.assert_public_url`).
- For respx-based hydration tests, monkeypatch `net.host_is_public` (or
  `socket.getaddrinfo`, as `test_media.py` already does) so no real DNS runs.
- Full suite must stay green with **zero behavioral assertions changed**.

### Acceptance
- `uv run pytest` green; no new network in tests; `media.py` and `feeds.py`
  no longer contain duplicate fetch/description logic.

## 5. Step 2 — HN link-post hydration before ranking

### Config (`daily_digest/config.py`)
```python
@dataclass
class HnCfg:
    enabled: bool = True
    min_points: int = 30
    hits: int = 60
    hydrate: bool = True        # fetch target-page descriptions for link posts
    hydrate_limit: int = 12     # bounded: max pages per run
```

### New function (`daily_digest/article.py`)
```python
def hydrate_hn_links(
    items: list[Item],
    config: Config,
    client: httpx.Client | None = None,
) -> list[Item]:
    """Hydrate AI-relevant HN link posts with empty/thin summaries.

    - candidates: source == "hn", summary < MIN_DESCRIPTION_CHARS,
      external http(s) URL (not news.ycombinator.com/item?id=...),
      title matches config.sources.feeds.topics (the same broad AI filter
      balanced_pool uses — don't waste requests on off-topic links);
    - order by points desc, take config.sources.hn.hydrate_limit;
    - hydrate_item() per item, best-effort;
    - returns a NEW list (Items are frozen); never raises.
    """
```

If `client is None`, open a short-lived `httpx.Client(timeout=8.0,
follow_redirects=False)` — `net.get_public` handles redirects itself.
Log one summary line: `hn hydration: 3/7 link posts hydrated`.

### Pipeline integration (`daily_digest/pipeline.py`)
Insert **after** the mute block / empty-digest early return and **before**
feedback aggregation + `balanced_pool`:

```python
# 2b. HN link hydration: link posts carry no Algolia story_text, so the
# editor pool and the writer would otherwise see title-only items.
# Best-effort quality step — failures never degrade the run.
if config.sources.hn.hydrate:
    fresh = hydrate_hn_links(fresh, config)
```

Why before `balanced_pool`: the pool's HN relevance filter and the editor's
candidate lines both read `title + summary`; hydrating after selection would
only fix the writer, not the pool.

### Failure modes
- Page blocked / 429 / timeout / >2 MB → item unchanged, counted as not
  hydrated, no warning spam (debug-level per item, one INFO summary line).
- All hydration fails → pool unchanged, digest unchanged, exit code unchanged.
- Worst-case latency: 12 pages × 8 s sequential ≈ 96 s. Expected is ~5–10 s.
  If the live run shows this is too slow, lower `ARTICLE_TIMEOUT` to 6 s or
  hydrate with a 4-worker thread pool — decide from measured live data, not
  upfront.

### Tests
New `tests/test_hn_hydrate.py` (respx + monkeypatched `host_is_public`):
1. HN link post, empty summary, page with `og:description` → non-empty summary,
   same uid/url/points, new list, original list untouched.
2. HN self post (`news.ycombinator.com/item?id=...`) → not fetched.
3. Off-topic HN title → not fetched (respx asserts zero calls).
4. On-topic HN with `points=None` still considered (points treated as 0).
5. `hydrate_limit=1` with two candidates → only the higher-points item fetched.
6. Page returns 500 / times out / 3 MB body → item unchanged, no raise.
7. `config.sources.hn.hydrate=False` → no client created (monkeypatch
   `httpx.Client` to raise if constructed).
8. Pipeline wiring: `run_day` with a patched `fetch_all` returning one HN link
   post; respx the target page; assert the item reaching `balanced_pool`
   (monkeypatch `pipeline.balanced_pool` to capture its input) has the hydrated
   summary; exit code and degraded flag unchanged.

### Acceptance (live)
- `uv run daily-digest run --force` logs `hn hydration: N/M`.
- No selected HN item renders "No description provided".
- Run still exits 0 and is not degraded by hydration failures.

## 6. Step 3 — Tech News source-diversity guard

### Config
Add a kill switch for reversibility:

```python
@dataclass
class LlmCfg:
    ...
    diversify_tech_news: bool = True
```

### New module `daily_digest/ranking/diversify.py`
```python
MIN_REPLACEMENT_SUMMARY_CHARS = 80

def diversify_tech_news(
    ranked: list[RankedItem],
    pool: list[Item],
    config: Config,
    adjustments: dict[str, float] | None = None,
    *,
    max_per_source: int = 1,
) -> list[RankedItem]:
    """Replace duplicate-source tech_news picks with qualified unused candidates.
    Papers and tools_releases are never touched.
    """
```

Algorithm (deterministic, logged):
1. Index `tech_news` positions in `ranked`; keep the **first** occurrence per
   source (highest editor importance — the hero/secondary stay).
2. For each duplicate occurrence (processed from the lowest-ranked one first):
   - build candidates from `rank_heuristic(pool, config, adjustments)`:
     `section == "tech_news"`, uid not already selected, source not already at
     the cap, `len(item.summary) >= MIN_REPLACEMENT_SUMMARY_CHARS`;
   - take the best remaining candidate (heuristic order = score order);
   - replace the duplicate **at its position** (order/top_n shape preserved),
     using the heuristic `why` line and `section="tech_news"`;
   - if no qualified candidate exists → keep the duplicate (never pad).
3. Log: `diversify: replaced <title> (<source>) with <title> (<source>)`.

The quality gate is intentionally simple: a replacement must already carry a
real description (≥80 chars). Lab/press/analysis feed items and hydrated HN
posts pass; thin vendor posts and un-hydrated HN links do not. This answers the
critic's objection that a bare per-source cap just picks a different thin item.

### Integration (`daily_digest/ranking/__init__.py`)
```python
ranked = rank_with_llm(items, llm_client.chat, config, reader_context)
if config.llm.diversify_tech_news:
    ranked = diversify_tech_news(ranked, items, config, adjustments)
return ranked[: config.llm.top_n], "llm"
```
Apply the same guard on the heuristic branch before slicing, so fallback mode
is consistent.

### Prompt
Append one sentence to `SYSTEM_PROMPT`:
`"Prefer at most one tech_news item per source."`
Update `GOLDEN_EDITOR` in `tests/test_profile.py` accordingly.

### Tests (`tests/test_ranking.py` + `tests/test_diversify.py`)
1. Two `huggingface_blog` tech picks + unused `deepmind_blog` candidate
   (summary ≥80) → one HF pick replaced by DeepMind; positions preserved;
   papers/tools untouched; `top_n` respected.
2. No unused candidate → duplicates kept, no padding.
3. Candidate summary <80 chars → not used, duplicate kept.
4. Candidate from a source already at the cap → skipped.
5. `diversify_tech_news=False` → no change.
6. `select()` applies the guard before `top_n` slicing (LLM branch with
   `FakeLlmClient`, and heuristic branch).
7. Feedback contract: replaced items keep their own uid; no duplicate
   `data-uid` in a rendered digest.

### Acceptance (live)
- Tech News shows ≥2 distinct sources whenever the pool has qualified
  candidates (target: 3 distinct when available).
- The digest is not padded: if only thin candidates exist, the section may run
  with 2 items.

## 7. Step 4 — `daily-digest health` (per-feed status)

### Refactor `sources/feeds.py`
Extract a single-feed helper so `fetch_feeds` and `check_feeds` cannot drift:

```python
def _fetch_entry(
    client: httpx.Client, entry: FeedEntry, cfg: FeedsCfg
) -> list[Item]:
    """Fetch + parse one feed. Raises on HTTP/parse/size errors."""

@dataclass(frozen=True)
class FeedHealth:
    name: str
    url: str
    label: str
    ok: bool
    item_count: int = 0
    error: str = ""

def check_feeds(client: httpx.Client, cfg: FeedsCfg) -> list[FeedHealth]:
    """Per-feed status; never raises, never hydrates (fast)."""
```

`fetch_feeds` keeps its current contract (items, raise only if **all** feeds
fail) but is reimplemented on top of `_fetch_entry`.

### CLI (`daily_digest/cli.py`)
```python
def cmd_health(config: Config, args: argparse.Namespace) -> int:
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        health = check_feeds(client, config.sources.feeds)
    for feed in health:
        status = "OK  " if feed.ok else "FAIL"
        line = f"{status} {feed.name}: {feed.item_count} items"
        if not feed.ok:
            line += f" — {feed.error}"
        print(line)
    ok = sum(1 for feed in health if feed.ok)
    print(f"feeds: {ok}/{len(health)} healthy")
    return 0 if ok else 1
```

- Subparser: `health` — "per-feed status for the curated feed source".
- Handler mapping + README command table entry.
- `smoke` stays as the all-sources live check; `health` is the feed-level
  drill-down (20 feeds, partial failures visible).

### Tests (`tests/test_health.py`)
1. `check_feeds`: one 200 feed (fixture XML) + one 500 feed →
   `[FeedHealth(ok=True, item_count=N), FeedHealth(ok=False, error=...)]`.
2. Malformed XML → `ok=False`, no raise.
3. `cmd_health` prints `OK`/`FAIL` lines and `feeds: 1/2 healthy`, returns 0
   (capsys + respx).
4. All feeds fail → returns 1.
5. `check_feeds` does **not** hydrate article pages (respx asserts only feed
   URLs are requested).

### Acceptance (live)
- `uv run daily-digest health` prints 20 feed lines and exits 0.
- A temporarily broken feed (e.g. point one entry at a 500 URL in a scratch
  config) shows `FAIL` with the error, exit 0 while other feeds are healthy.

## 8. Docs / config / README

- `config.example.yaml`: extend the `hn` block with `hydrate: true` /
  `hydrate_limit: 12`; add `llm.diversify_tech_news: true` with a one-line
  comment.
- `README.md`:
  - commands table: `| uv run daily-digest health | Per-feed status for the 20 curated feeds |`
  - "How it works": one clause noting HN link posts are hydrated from the
    target page before ranking.
- `docs/tech-news-sources.md`: new section
  "HN hydration, source diversity and feed health (2026-11-19)" with the live
  evidence from this sprint (hydration counts, distinct Tech News sources,
  health output).
- `docs/feature-roadmap.md`: short note that the archive/search track (F8+)
  is intentionally deferred until ≥10 blob days.

## 9. Verification matrix

| Check | Command | Expected |
|---|---|---|
| Full suite | `uv run pytest -o addopts=''` | all green (298 existing + ~15 new) |
| Feed health | `uv run daily-digest health` | 20 lines, `feeds: 20/20 healthy`, exit 0 |
| Real run | `uv run daily-digest run --force` | exit 0, no new degraded causes |
| Hydration log | `logs/daily-digest.log` | `hn hydration: N/M link posts hydrated` |
| Summary quality | grep `output/latest.html` | no `"No description provided"` for HN items |
| Diversity | section counts in `latest.html` | Tech News ≥2 distinct sources (3 when available) |
| Contracts | DOM check + `digest-data` blob | 12 uid / 12 like / 12 ask, blob intact |
| Popup | `uv run daily-digest open --web latest` | exit 0 |
| Visual | screenshots light/dark | no layout regression |

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Hydration adds latency (worst 12×8 s) | bounded limit, per-page timeout, one INFO summary; measure live, then tune timeout/concurrency if needed |
| Hydration fetches untrusted HN targets | `net.get_public`: http(s) only, per-hop redirect validation, private-IP block, 2 MB cap |
| Diversity forces a weaker item | only replace when a candidate has a real description (≥80 chars); otherwise keep the duplicate |
| Prompt change shifts editor behavior | one sentence, golden test updated, live run compared against 2026-11-19 baseline |
| Refactor breaks media/feed hydration | step 1 is behavior-preserving with moved tests; full suite gate before step 2 |
| Health command doubles feed traffic | manual command only, never called by `run_day` |
| New config keys ignored by old configs | dataclass defaults keep behavior; `_merge_obj` already warns on unknown keys |

## 11. Rollback

- Each step is one commit; revert the commit to remove the behavior.
- `sources.hn.hydrate: false` disables HN hydration without a revert.
- `llm.diversify_tech_news: false` disables the diversity guard.
- `health` is additive (new command only) — deleting the handler removes it.
- No state, feedback, archive, or template migration exists in this sprint, so
  there is nothing to un-migrate.

## 12. Commit plan (each independently shippable)

1. `refactor(net,article): shared safe fetch and article description helpers`
2. `feat(hn): hydrate link-post descriptions before ranking`
3. `feat(ranking): one tech-news item per source`
4. `feat(cli): per-feed health command`
5. `docs(sources): HN hydration, diversity and health evidence`

## 13. Deferred: archive/search (the agreed trigger)

Do not build the archive index in this sprint. Revisit when:

- there are **≥10 digest days carrying a `digest-data` blob**, or
- the owner has actually searched the archive ≥3 times and `rg` is no longer
  good enough.

When triggered, the first archive step is a **canonical record writer**
(`output/records/YYYY-MM-DD.json` written from `ranked` + `mode` + `overview`
at the end of `run_day`) — not parsing the lossy blob. Search then uses SQLite
FTS5 (verified available: SQLite 3.53.1) with Vietnamese diacritic folding,
full-replace per date, `latest.html` excluded, and the legacy 2026-11-18 day
marked unindexed.
