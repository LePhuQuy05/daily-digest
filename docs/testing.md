# Testing notes

## Run the suite

```powershell
uv run pytest -o addopts=''
```

- **377 tests**, offline by default.
- CI runs the same command on `windows-latest` for every push and pull request.
- Dependencies are pinned in `uv.lock`; CI installs with `uv sync --locked`.

## What is covered

| Area | Examples |
|---|---|
| Sources and normalization | HN hydration, HF/arXiv parsing, feed health, merge/dedupe provenance |
| Ranking | LLM selection, heuristic fallback, diversity, mute/always rules |
| Pipeline | Idempotency, `--new-only`, backfill, degraded exit codes, atomic writes |
| Rendering | Section fronts, XSS escaping, safe links, print/token invariants |
| Demo | Bundled fixture render, coverage, no network or key requirement |
| Overview | Marker parsing, duplicate cleanup, coverage guarantee, every fallback mode |
| Interaction | Feedback toggles, saved/undo, bridge read layer, ask failure paths |
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
