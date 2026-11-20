# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses semantic versioning.

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
