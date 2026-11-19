# Spec: F1 · F2 · F4 · F5 — build exactly per this document

*Approved architecture (architect + critic review, 2026-11-19). A goal prompt points
here; this file is the single source of truth for implementation.*

## Features

- **F1 Feedback loop** — 👍/👎/🔖 buttons on each card in the pywebview popup.
  Persist to `feedback.jsonl`: append-only via `os.open(O_APPEND|O_CREAT|O_WRONLY)` +
  ONE `os.write()` of UTF-8 bytes per line (never buffered text mode); each line
  `{"v":1, ts, date, uid, action, snapshot}`; truncate snapshot summaries ~1000 chars.
  Aggregate TWO channels: `rating` (last of like/dislike wins per uid), `save`
  (save/unsave); 14-day window; tolerant reader (skip bad/partial lines, never raise).
  Effects: (a) bounded shared `reader_context` block in editor+writer prompts
  (≤10 liked + ≤10 disliked titles, 80 chars each, pinned titles, 14d window);
  (b) heuristic topic adjustment `adj[t]=clamp(0.25·(likes−dislikes), ±1.0)` applied
  with ITEM-LEVEL clamp `clamp(Σ adj over hits, ±1.5)`; (c) 🔖 pinned "Nhìn lại"
  section: 5 newest save-snapshots + "+N mục đã lưu cũ hơn" note, unsave clears,
  pinned∩pool drops from pinned, pinned bypasses mute + seen-set.
- **F2 Ask-this-item** — per-card chat drawer. Bridge `ask(uid, question)` → LLM
  grounded ONLY in title+abstract+llm_summary; answer in question's language ≤120
  words. Single-shot budget: timeout 45s, 1 attempt (not the 90s×3 run profile).
  Never raises: no key/offline/timeout → polite message. JS must `.catch`.
- **F4 Profile context** — `profile.md` free text; `llm.profile_file`,
  `llm.profile_max_chars=600`, word-boundary truncation; injected via the same
  reader_context block into editor/writer/ask prompts. Missing → "" + warning.
- **F5 Keyword rules** — `interests.mute[]`: hard-drop post-merge pre-pool,
  case-insensitive substring on title+summary; mute beats always; WARN when >80%
  of fresh dropped; visible digest note when post-mute pool empty; exit stays 0.
  `interests.always[]`: heuristic bonus 3.0 + `★ALWAYS` prefix in candidate lines +
  `{always_rule}` line in the editor prompt.

## Hard constraints

1. Popup = separate short-lived pythonw process, possibly N concurrent. Popups must
   NOT write `state.json`; never call `util.load_json` from popup code (it renames
   corrupt files = a write). Use a dedicated side-effect-free reader → `{}` on error.
2. Item data for the popup = JSON blob embedded in the digest HTML:
   `<script type="application/json" id="digest-data">{{ digest_data | tojson }}</script>`.
   Plain dicts only (datetime is not JSON-serializable); top-level `"date"` plus
   uid→{title,url,source,points,citations,summary,llm_summary,why,section}.
   Extractor regex: `<script[^>]*\bid="digest-data"[^>]*>(.*?)</script>` with
   `re.DOTALL` + a roundtrip test parsing the REAL rendered template tag.
3. Bridge = one `DigestBridge` class, exactly two methods:
   `feedback(uid, action) -> dict` (exception-proof; return `{"ok": False, ...}`
   rather than raise — Python exceptions reject the JS Promise) and
   `ask(uid, question) -> str`. JS reveals bridge-only UI only when
   `typeof window.pywebview?.api?.feedback === 'function'`. Same template is opened
   in browsers (`open --web`, no bridge): buttons/drawer hidden, zero JS errors.
4. Popup LLM session: read state.json LAZILY at first ask (not at boot — avoids the
   spawn-vs-save race), side-effect-free; fallback `"ses_popup_"+token`; never save_json.
5. Prompt changes: `{reader_context}` slot after the interests line in
   SYSTEM_PROMPT and SUMMARIZE_SYSTEM_PROMPT, `{always_rule}` in the editor prompt;
   update ALL `.format()` call sites in the SAME commit; empty inputs must produce
   byte-identical prompts to today's (golden test); build reader_context by
   concatenation/f-strings only (titles may contain `{}` braces).
6. No new heavy deps. Quality features never affect exit codes 0/1/2 or block
   delivery — every new pipeline step inside try/except with empty-default fallback.
   Tests fully offline; extend conftest autouse guards (no real popup/webview).

## Day-0 probes (run before feature code; record results)

1. `grep -rn "SYSTEM_PROMPT\|_candidate_line\|\.format(" tests/` — byte-identity already enforced?
2. Confirm `select()` with an empty pool → empty-but-valid digest, no exception.
3. Concurrency: 2 subprocesses × 500 appends + a 12KB-line case → all-or-whole-line
   loss only; `os.replace` vs reader loop on state.json → PermissionError rate.
4. OpenCode Go: two concurrent chats with distinct `ses_popup_*` ids → expect 200s.

## Implementation order (suite green at every step)

1. F5 rules → 2. F4 profile (+ golden byte-identity tests) → 3. Data plumbing
(blob + extract + bridge-only scaffold) → 4. F1 feedback (+ "Nhìn lại" + pipeline
consumption) → 5. F2 ask → 6. Polish (`feedback --stats` CLI, README,
config.example.yaml, profile.md template).

## Acceptance evidence (real command output required)

- `uv run pytest` fully green, with new tests: golden prompts · hostile-title blob
  roundtrip (`</script><script>alert(1)`, braces, emoji, newline) + `date` in blob +
  latest.html self-pairing · extract-vs-real-template-tag · concurrent appends
  (incl. 12KB line) · aggregate flip (like→dislike counts once) · item-level clamp
  ±1.5 · mute >80% WARN + empty-pool note + exit 0 · mute beats always · pinned
  lifecycle · ask never-raises · popup state reader creates NO `state.json.corrupt`.
- Live smoke: popup 👍 appends a parseable line; ask answers with key / polite
  message without; `open --web` no buttons, no JS errors; old digest → inert
  buttons; two popups rapid cross-clicks all parse; `run --force` delivers
  digest+toast+popup with feedback context in the editor prompt.
- Implement all four features; if a probe contradicts a decision, adapt and note
  the deviation in this file.
