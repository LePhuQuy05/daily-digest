# Writer quality harness and writer v2

This is the measurement layer for the writer, added before changing the en/ja
generation path.

## Why

Vietnamese (`vi`) was consistently good for the day overview and per-item
summaries, while English (`en`) and Japanese (`ja`) were weak. Before rewriting
prompts, the writer has deterministic defects that can look like model quality:

- summary text can be clipped by the CSS line clamp;
- ja source abstracts were truncated to 400 chars while vi/en got 1200;
- ja summaries were hard-capped at 180 chars;
- kana-gate drops were silent;
- the overview parser split paragraphs into sentences and then dropped middle
  points when `MAX_POINTS` was exceeded;
- overview truncation cut the tail, where the takeaway lives;
- one call produced both the overview and every item summary.

## Harness

`daily_digest/writer_quality.py` contains pure metrics. `tools/writer_eval.py`
scores archived edition snapshots offline; it never calls the network.

```powershell
# Current snapshot(s)
uv run python tools/writer_eval.py --editions-dir output/editions

# Save a baseline
uv run python tools/writer_eval.py --editions-dir output/editions `
  --baseline output/quality-baseline.json

# Compare after a writer change
uv run python tools/writer_eval.py --editions-dir output/editions `
  --compare output/quality-baseline.json
```

Metrics:

- summary coverage and average length;
- specificity (digit or technical token);
- generic phrase ratio per locale;
- target-locale match;
- approximate visible-length fit;
- overview point/rest structure and single-ref ratio.

The visible-length number is a conservative estimate, not a browser
measurement. Pair it with the screenshot/print checks.

## Baseline

Current vi archive snapshot:

```text
items=20 summary=20/20 avg=350.4 specific=0.8 generic=0.15
locale=1.0 visible=1.0 points=6 rest=5 single=0.0 pass=True
```

en/ja fixtures under `tests/fixtures/quality/` prove the metrics discriminate
specific localized output from generic English output.

## writer v2

`llm.writer_v2` is **false by default**:

```yaml
llm:
  writer_v2: false
```

When enabled, the writer:

- batches item summaries (12 per call) with absolute item indices;
- writes the overview in a separate call from titles, sections, summaries, and
  short source snippets;
- uses locale-native style cards/examples/anti-patterns in
  `daily_digest/ranking/writer_prompts.py`;
- keeps stage fallbacks independent;
- marks partial batches degraded in the pipeline/localize path;
- runs under one monotonic deadline.

The current-edition `localize` path uses the same writer, so a language switch
still preserves the ordered item set and never fetches/ranks.

## Rollout gate

Do not enable `writer_v2` on the 09:00 path until:

- absolute blind metrics pass (fact/specificity/generic/visible/rest/coverage);
- no silent kana/truncation drops;
- vi does not regress;
- blind human review of 5–10 items per locale scores mean ≥4 and no item ≤2;
- full suite, demo, print/A4, and Windows CI are green.

If the harness does not improve en/ja, keep the deterministic fixes and A/B a
per-locale writer model or vi→en/ja translation; do not enable v2 by default.
