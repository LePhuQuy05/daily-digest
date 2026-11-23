# Testing notes

## Run the suite

```powershell
uv run pytest -o addopts=''
```

- **564 tests**, offline by default.
- CI runs the same command on `windows-latest` for every push and pull request.
- Dependencies are pinned in `uv.lock`; CI installs with `uv sync --locked`.

## What is covered

| Area | Examples |
|---|---|
| Sources and normalization | HN hydration, HF/arXiv parsing, feed health, merge/dedupe provenance |
| Ranking | LLM selection, heuristic fallback, diversity, mute/always rules |
| Pipeline | Idempotency, `--new-only`, post-select historical fill (day-2+, never yesterday), shortfall/count dateline, degraded exit codes, atomic writes |
| Digest size | 1–30 policy, preferences, CLI override, short pools, historical archive pool, backfilled provenance, morning backup, archived bridge guard |
| Rendering | Section fronts, paper metadata dates, XSS escaping, safe links, print/token invariants |
| Locales | `vi`/`en`/`ja` catalog parity, precedence, `--lang`, dates, JS messages, Japanese splitting/truncation, prompts, settings and backups |
| Edition localization | Snapshot round-trip, legacy HTML recovery, item-set identity, no fetch/rank, target-locale fallbacks, image preservation, one backup/spawn, lock/path/hash safety |
| Cover hero | OG/landscape gate, 70% contrast, credit escaping, print reset, image-failure fallback |
| Demo | Bundled fixture render, coverage, no network or key requirement |
| Overview | Marker parsing, duplicate cleanup, coverage guarantee, every fallback mode, legacy rail |
| Section briefs | One brief per non-empty section, ref/coverage validation, kana gate, deterministic fallback, old-snapshot rail, localize regeneration |
| More band | Full summary per overflow item, no clamp, actions/Ask, print columns |
| Interaction | Feedback toggles, saved/undo, bridge read layer, ask failure paths |
| Writer quality | vi/en/ja detection, fact recall, visible budgets, stage isolation, snapshot scoring, fallback exclusion, regression gate |
| Desktop | Tray/shortcut/task installation behind mocks; no real desktop changes |

## What is mocked

- HTTP requests use `respx` fixtures.
- LLM calls use fake clients with deterministic responses.
- Desktop/window/toast integrations are isolated so the suite can run headlessly.

## Deliberately not tested

- Live source APIs and real model providers (they are nondeterministic and rate-limited).
- Actual Windows toast delivery and the native `pywebview` window.
- Pixel-perfect visual diffs. UI behavior is covered by template/CSS assertions and manual checks.

## Known gaps

- No coverage gate yet; the suite focuses on failure modes rather than a percentage.
- CI is Windows-only. The fetch/rank/render stages are not tied to Windows, but only Windows is currently verified.
- A ranking-quality evaluation harness would be the next meaningful test layer.
