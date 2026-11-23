# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses semantic versioning.

## [Unreleased]

### Added

- First-class Vietnamese (`vi`), English (`en`), and Japanese (`ja`) locales for UI chrome and generated content; `vi` remains the default.
- `run --lang` and `demo --lang`; `ja-JP`, `JA`, and `ja_JP` normalize to `ja`. `--lang` is a one-off override and implies `--force`.
- Combined size + language settings dialog. One Apply writes both preferences atomically, creates a unique morning backup first, and spawns one rebuild.
- Automatic historical fill: when a user has saved a digest size (or passes `--count`), a short digest is topped up after selection from day-2 or earlier, never from yesterday, until the target or the local archive is exhausted. The dateline shows `actual/requested` and `+N older`; `--no-backfill` keeps a run fresh-only. The scheduled 09:00 run uses this automatically.
- Section briefs replace the single global day-overview rail: one bounded brief per non-empty section, generated in one batched call with a deterministic fallback, inline refs, and `coverage_refs` for every remaining item. Older snapshots without briefs keep the legacy rail.
- The overflow `more` band now renders each item's full summary on screen and in print; the summary is a grid area below the metadata and is never line-clamped there.
- Structured notices: shortfall and `writer_partial` can render together in one status strip, and localization recomputes each notice from its key and params.
- `llm.auto_batch_long` (default `true`) batches item summaries through the writer-v2 12-item path when a digest has more than 16 items, so a 30-item digest does not lose summaries to one truncated response.
- Source expansion: add Epoch AI, Apple ML, Ai2, vLLM blog, PyTorch blog, Meta Engineering, Modal, Alignment Forum, METR, Vals AI, and Transformer Circuits feeds; PyTorch uses topic filtering plus title excludes to drop community/award posts. Add arXiv `stat.ML`, `cs.RO`, `cs.SE`, `cs.CR` with cap 30 and an LLM/AI title+abstract filter. `health` reports 31/31 feeds.
- Overflow section briefs now render in a full-width `section-more` index with a heading/count and compact rows: actions sit beside the title, Ask stays per item, and the band collapses to one column at ≤920px with a two-column print layout. The count uses `section_more_count` deliberately so English singular reads “1 more” instead of the existing “1 stories”.
- Masthead language selector for direct switching; demo mode navigates between pre-rendered vi/en/ja files.
- `localize --lang` localizes today's selected edition without fetching or re-ranking; a versioned `output/editions/digest-YYYY-MM-DD.json` sidecar preserves ordered items, paper dates, overview points, pinned items, path, and HTML hash.
- Japanese typography and print rules, localized AI-summary label, toast body, dates, section titles, and heuristic fallbacks.
- Offline writer-quality harness (`tools/writer_eval.py`) and writer v2 behind `llm.writer_v2=false`: ja abstract/cap fixes, paragraph-aware overview points, bounded rest lists, takeaway preservation, source-aware batches, and independent overview/fallback stages.
- Writer v2 follow-up: stale localize fallback state is cleared, source failures still degrade; transport failures stay per batch/overview; partial batches render a notice; ja overlong summaries trim at a sentence boundary; and the harness gates source-anchored fact recall.

### Changed

- Full-locale output intentionally replaces the previous mixed vi/en behavior: `vi` now has Vietnamese summaries and `why` lines, and `en` has English chrome + content.
- `latest.html` is refreshed only for today; `--date` backfills no longer clobber it.
- Backups now use `-morning`, `-morning-2`, … and never overwrite an earlier copy.
- Language-only changes keep the current ordered item set and regenerate localized content; size changes still rerun the pipeline and may select a different set.
- Images are read from the current HTML data URIs; localize does not depend on the media cache.

### Fixed

- Archived digests keep their baked locale and remain read-only; legacy size bridge methods still work.
- Japanese overviews split on `。！？` plus closing quotes, protect versions/URLs from ASCII-dot splitting, normalize full-width markers, and remove partial `[[` artifacts.

- Localize writes are serialized with a cross-process lock and unique temp files; writes preserve `-2.html` paths and refuse stale snapshot hashes.
- Detached `localize` failures now restore the previous language preference and write a status file; the open window polls and surfaces the error.

## [0.1.1] - 2026-11-21

### Added

- Hero cover treatment for landscape OG leads: a 70% ink wash, inline print-visible credit, image-failure fallback, and regression coverage for the gate, contrast, and print styles.
- Paper cards now show the publication date (`DD.MM.YYYY`) in the metadata line.
- Configurable digest size: 1–30 items, default 12; `preferences.json`, `run --count`, and a popup size dialog. Size changes rerun the pipeline and back up the morning edition.
- The zero-key demo now includes a generated abstract cover fixture, so the treatment is visible without waiting for an OG-led day.

## [0.1.0] - 2026-11-20

### Added

- Windows desktop digest delivered by scheduled task, popup window, toast, tray icon, and `Ctrl+Alt+D`.
- Six source families and 20 curated feeds: Hacker News, Hugging Face Daily Papers, arXiv, Emergent Mind, alphaXiv, AI-lab blogs, tech press, and GitHub releases.
- Two LLM roles: an editor that ranks ~12 items with a one-line rationale, and a writer that adds summaries and a day overview.
- Inline overview citations with click-to-scroll/focus/highlight, plus a deterministic `Còn lại hôm nay` coverage line.
- Interactive digest: thumbs feedback, save/unsave with undo, saved-articles modal, grounded item Q&A, light/dark themes, and a print stylesheet.
- Zero-key `daily-digest demo` command that renders bundled fixtures without network or LLM calls.
- 377 offline tests and a Windows GitHub Actions workflow.

### Changed

- Every model and source boundary has a deterministic fallback; a degraded digest still ships.
- Daily runs are idempotent, use a 7-day seen-set, and write digests atomically.
- `config.yaml` and runtime state are git-ignored; configuration examples remain tracked.

### Security

- API keys are read from environment variables or `.env` and are redacted from `print-config`.
- Feed text is treated as data, model output is parsed as JSON, and rendered HTML is autoescaped.
- No analytics, telemetry, or third-party UI scripts.
