# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses semantic versioning.

## [Unreleased]

### Added

- First-class Vietnamese (`vi`), English (`en`), and Japanese (`ja`) locales for UI chrome and generated content; `vi` remains the default.
- `run --lang` and `demo --lang`; `ja-JP`, `JA`, and `ja_JP` normalize to `ja`. `--lang` is a one-off override and implies `--force`.
- Combined size + language settings dialog. One Apply writes both preferences atomically, creates a unique morning backup first, and spawns one rebuild.
- Masthead language selector for direct switching; demo mode navigates between pre-rendered vi/en/ja files.
- Japanese typography and print rules, localized AI-summary label, toast body, dates, section titles, and heuristic fallbacks.

### Changed

- Full-locale output intentionally replaces the previous mixed vi/en behavior: `vi` now has Vietnamese summaries and `why` lines, and `en` has English chrome + content.
- `latest.html` is refreshed only for today; `--date` backfills no longer clobber it.
- Backups now use `-morning`, `-morning-2`, … and never overwrite an earlier copy.

### Fixed

- Archived digests keep their baked locale and remain read-only; legacy size bridge methods still work.
- Japanese overviews split on `。！？` plus closing quotes, protect versions/URLs from ASCII-dot splitting, normalize full-width markers, and remove partial `[[` artifacts.

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
