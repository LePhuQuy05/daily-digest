# Architecture

Daily AI Digest is a local pipeline with a deliberately small surface area: fetch, normalize, rank, summarize, render, deliver. The design goal is not maximum throughput; it is **a digest that still arrives when one dependency fails**.

## Boundaries

| Boundary | Components | Behavior |
|---|---|---|
| External network | HN, HF Daily Papers, arXiv, Emergent Mind, alphaXiv, RSS/Atom, OpenAlex | Each source fails independently; errors are reported, not raised through the pipeline |
| Probabilistic | Editor LLM, writer LLM, Ask | Structured outputs are parsed and validated; each has a deterministic fallback or a safe refusal |
| Deterministic | Normalization, merge/dedupe, seen-set, ranking fallback, rendering, atomic writes | Reproducible and covered by the offline suite |
| Local-only | `state.json`, `feedback.jsonl`, `preferences.json`, `output/`, `logs/` | Never uploaded by the app; API keys come from the environment |

## Request lifecycle

1. **Trigger** — Windows Task Scheduler at 09:00, the tray refresh action, or `daily-digest run`.
2. **Fetch** — source adapters run with bounded timeouts; failures are collected per source.
3. **Normalize and merge** — items are canonicalized; the same paper from multiple sources becomes one item with provenance.
4. **Filter and enrich** — the 7-day seen-set removes repeats; OpenAlex adds citation counts.
5. **Rank** — the editor LLM selects the requested 1–30 items (default 12) and writes a one-line justification; a keyword/points/recency ranker takes over if the editor is unavailable. A user size change reruns this stage and the writer, with a morning-digest backup before overwriting today's edition.
6. **Summarize** — the writer LLM adds 2–3 sentence summaries and the day overview; raw abstracts and a heuristic overview are the fallback.
7. **Render and deliver** — Jinja produces one self-contained HTML file; the popup and toast open it.

## Failure policy

| Failure | Policy |
|---|---|
| Missing API key | Heuristic ranking; digest marked degraded; exit `1` |
| One source unavailable | Continue with the remaining sources; `health` reports per-feed status |
| Editor timeout / 401 | Heuristic ranking; no empty digest |
| Writer timeout / invalid JSON | Keep raw abstracts and a deterministic overview |
| Writer omits an item from the overview | `ensure_coverage` adds a `Còn lại hôm nay` reference line |
| `latest.html` locked / process dies | Atomic write; keep the previous good file |
| Feed text contains instructions | Treat as data; model output is parsed as JSON, never executed; HTML is escaped |

## Data flow

- API keys: environment or `.env` → LLM provider only; never logged.
- Selected titles, abstracts, `profile.md`, recent feedback: sent to the configured LLM provider for ranking/summaries/Ask.
- Digest, state, feedback, saved items: local disk only.
- No telemetry, analytics, or third-party UI scripts.

## Key files

| File | Responsibility |
|---|---|
| `daily_digest/pipeline.py` | Orchestration, idempotency, fallback policy |
| `daily_digest/ranking/llm.py` | Editor/writer prompts, JSON parsing, overview validation |
| `daily_digest/overview.py` | Citation marker parsing, labels, coverage guarantee |
| `daily_digest/render.py` | Jinja context and digest data blob |
| `daily_digest/popup_bridge.py` | Bridge for feedback, saved items, and Ask |
| `templates/` | HTML, CSS, and vanilla JS; no frontend build step |

See also: [testing notes](testing.md), [source catalog](tech-news-sources.md), and the [overview references plan](overview-references-plan.md).
