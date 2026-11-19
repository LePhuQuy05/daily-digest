# Feature Roadmap — What to Build Next

*Synthesized 2026-11-19 from two halves: (1) creative-framework analysis of our own
architecture (constraint/negation/adjacent-possible/reformulation), and (2) a cited
landscape survey of comparable products — `docs/feature-ideas-landscape.md`. Every
candidate is framed as a testable hypothesis, prioritized by impact × effort × fit
with the tool's philosophy (local · single-user · reliable-unattended · keyless-first).*

## The three blind spots the analysis found (why these tiers)

1. **No feedback path** — the editor LLM picks every day but never learns what you liked
2. **Items vanish after their day** — no save-for-later, no resurfacing; the seen-set only dedupes
3. **No memory across days** — each digest is a blank slate; no trends, no "you read this already"

External evidence agrees: the strongest demand signal in the whole survey is
**history-based recommendation** (`zotero-arxiv-daily`: 6,166★ — out-stars plain
digests ~2:1), and every commercial research platform (Elicit Routines, alphaXiv
For-You) ships a "tell me what to keep current, learn from me" loop.

---

## Tier 1 — build next (highest impact ÷ effort)

### F1. Feedback loop: 👍 / 👎 / 🔖 (save) → the digest learns your taste
- **Hypothesis**: digest quality improves measurably within 1–2 weeks because the
  editor prompt gains evidence of your actual preferences; saved items resurface
  until handled. *Predicting: fewer off-topic picks, a "Nhìn lại" (look back)
  section you actually clear.*
- **Evidence**: zotero-arxiv-daily 6,166★ (recommend-from-library); alphaXiv
  For-You feed; Readwise Daily Review (spaced resurfacing); our hidden-constraint #1.
- **Design sketch**: pywebview JS→Python bridge buttons on each card → append to
  `state.json` (`likes`/`dislikes`/`saved` with uid + date) → (a) editor+writer
  prompts get a "reader's recent signals" block (liked topics/papers, disliked
  ones), (b) heuristic topic weights nudge ±, (c) saved items render in a pinned
  "Nhìn lại" section for up to 5 days until you clear them.
- **Effort**: medium (bridge + state + prompt injection + template section).

### F2. "Ask about this item" — chat sidebar in the popup
- **Hypothesis**: most follow-up questions ("does this beat X?", "is code released?")
  can be answered from the abstract + LLM knowledge without leaving the popup.
- **Evidence**: every research platform ships some version (Elicit, SciSpace,
  alphaXiv discussions); our adjacent-possible (pywebview bridge + existing
  LlmClient).
- **Design sketch**: `expose(ask(item_id, question))` → writer-model call with the
  item's abstract as context → answer renders in a small chat drawer per card.
  Falls back to "open in browser" if the LLM is down.
- **Effort**: medium.

### F3. Audio overview — nghe "Tổng hợp hôm nay"
- **Hypothesis**: the overview card is the highest-density 30 seconds of the digest;
  reading it aloud makes morning consumption hands-free.
- **Evidence**: paper-to-podcast is a 2025–26 category, not a gimmick (SciSpace
  Paper-to-Podcast, alphaXiv narration, researchpod.app); Windows SAPI TTS =
  keyless + offline.
- **Design sketch**: 🔊 button on the overview card → `System.Speech` (SAPI,
  Vietnamese voice if installed, else English fallback) speaks the overview;
  stop button; no cloud dependency.
- **Effort**: small.

### F4. Personal profile context — `profile.md`
- **Hypothesis**: one paragraph about your *current work* makes the editor's picks
  and why-lines dramatically more specific than a topic list can.
- **Evidence**: Elicit Routines ("tell the agent what to keep current") is
  commercial validation of exactly this; our reformulation ("editor knows ME, not
  just topics").
- **Design sketch**: `profile.md` at project root (free text, git-friendly) →
  first ~300 words injected into editor + writer system prompts → config knob to
  disable. `print-config` shows whether it's active.
- **Effort**: trivial.

### F5. Keyword include/mute rules
- **Hypothesis**: cheap, deterministic control beats LLM taste for known-noise
  ("mute: Solana, NFT" / "always include: vLLM").
- **Evidence**: Inoreader rules + Feedly filters are core, decades-old features.
- **Design sketch**: `interests.mute: []` / `interests.always: []` in config.yaml →
  fetcher-level drop (mute) + heuristic/editor boost pin (always).
- **Effort**: small.

## Tier 2 — strong, slightly bigger or situational

### F6. Weekly review (Chủ nhật)
Sunday digest: top 5 of the week + trend summary + "what you saved but didn't
read". Reuses the whole pipeline (`--date` backfill + aggregation). Evidence:
TLDR/The Batch archives; our negation ("important ≠ new").
**Effort**: medium.

### F7. Trend detection + chips
`state.json`'s seen map already encodes topic history → detect "agentic RL: 3 ngày
liên tiếp" → chip in the overview + injected into the editor prompt ("rising theme,
prefer"). Evidence: agents-radar style ecosystem digests; our adjacent-possible.
**Effort**: small–medium.

### F8. Search across the archive
`daily-digest search "quantization"` → full-text over `output/digest-*.html`
(plain-regex index, no deps) + a results page. Evidence: every newsletter ships
archive search; agent shortlist #5 (trivial).
**Effort**: trivial–small.

### F9. Same-topic grouping within a day
5 RLHF papers → one grouped card ("5 papers về RLHF hôm nay"). Writer-prompt
change + template. Evidence: how The Batch/TLDR cluster.
**Effort**: small.

## Tier 3 — later / situational

- **F10. Telegram/email channel** — for away-from-PC days; medium effort; only if
  you actually leave the PC in the morning.
- **F11. Expose the digest as an MCP server** — the 2026 pattern (Readwise MCP,
  Elicit MCP, alphaXiv MCP): let *other* agents query your archive. Big, but the
  natural next ecosystem move.
- **F12. Reading-time budget mode** — top_n as minutes, cards labeled with
  estimated read time.
- **F13. Generic RSS source** — the registry takes any feed; broadens coverage
  beyond our 5 vetted sources.

## Rejected (documented, with reasons)

- Community comments / multiplayer libraries / public leaderboards — cloud-only,
  violates single-user-local philosophy (flagged in the landscape doc).
- Browser-extension capture flows — Pocket is dead; Readwise covers that need
  better than we should.

---

## Implementation notes (deviations found by day-0 probes)

- **Append mechanism**: the spec's `os.open(O_APPEND)+os.write` probe FAILED on
  Windows (5 torn / 74 lost lines of 1000 under 2 concurrent writers — CRT
  `_O_APPEND` is seek-then-write). Replaced with `CreateFileW(FILE_APPEND_DATA)` +
  a single `WriteFile` (probe: 1000/1000 atomic, incl. 12KB lines). POSIX keeps
  the plain os.write path. Implemented in `feedback.py:_append_line`.
- **state.json race**: the os.replace-vs-reader probe measured 4602 errors/3s in
  a tight loop — confirming the lazy-read design: the popup reads the session
  only at the FIRST ask call, long after the run finished.
- **Endpoint sessions**: two concurrent chats with distinct `ses_popup_*` session ids both returned HTTP 200 — ephemeral popup sessions are safe.

*Sources: docs/feature-ideas-landscape.md (cited, checked 2026-11-19) + architecture
analysis in this repo's build history. GitHub star counts are drift-prone; treat as
order-of-magnitude demand signals.*
