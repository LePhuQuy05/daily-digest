# Daily AI Digest 📡

A Windows morning digest with everything you should know today as an AI engineer:
the best new research papers (arXiv + Hugging Face Daily Papers) and the top
tech/AI news (Hacker News), curated by **two LLMs**:

- 🧠 **The editor** (default: GLM 5.3) picks the ~12 items worth your time and writes a one-line *why it matters*
- ✍️ **The writer** writes a proper 2–3 sentence summary of every selected item — what it does, the key finding, and why it's relevant to you — plus a **"Tổng hợp hôm nay"** card at the top: a Vietnamese synthesis of the day's themes and the single most important takeaway (language configurable via `llm.overview_language`)

Every morning at **09:00** you get it two ways:
- 🪟 **Popup window** — a native window with the full digest opens on your desktop (paper links open in your browser)
- 🔔 **Toast** — a notification; clicking it opens the popup window

And you can summon it **any time**:
- 🖱️ **Tray icon** — an indigo "D" near the clock: click it → the digest pops up
- ⌨️ **Ctrl+Alt+D** — works from anywhere (registered on the Desktop shortcut)
- 🖥️ **Desktop shortcut** — double-click "Daily AI Digest"
- 🔁 Right-click the tray → **"Làm mới ngay"** re-runs the whole pipeline on demand (fetch + both LLMs + toast + popup)

The popup is **interactive**:
- 👍/👎 — teach the editor what you want more/less of (persists in `feedback.jsonl`; the editor and writer prompts learn from your last 14 days; run `daily-digest feedback` to see the stats)
- 🔖 Lưu — pin an item; it resurfaces in the **"Nhìn lại"** section of future digests until you click ✓ Đọc xong
- 💬 **Hỏi** — ask any question about an item right in the drawer; the answer is grounded only in that item's abstract + digest summary (needs the API key; politely declines without it)

Personalization:
- `profile.md` — write a paragraph about your current work; the editor picks *for your project*, not just your topic list (F4)
- `interests.mute: [NFT, crypto]` / `interests.always: [vLLM]` — deterministic keyword rules; mute is a hard drop that beats always (F5)

---

## Quick start (2 minutes)

```powershell
cd D:\Research\daily-digest

# 1. Add your OpenCode API key (from https://opencode.ai/console -> Account -> Personal API keys)
copy .env.example .env
notepad .env        # paste: OPENCODE_API_KEY=oc_sk_...

# 2. Run it right now (full fetch + LLM ranking + toast)
uv run daily-digest run --force

# 3. Verify the toast appears, click it, then relax: tomorrow 09:00 it's automatic.
```

The Task Scheduler job is **already installed** (name: `Daily AI Digest`). If you
ever need to redo it: `uv run daily-digest install-task` / `uninstall-task`.

> No key yet? It still works — ranking falls back to keyword+points heuristics
> and the digest is flagged *degraded* (exit code 1) until you add the key.

## Changing the LLMs (one line each)

Edit `config.yaml` (copy `config.example.yaml` to start):

```yaml
llm:
  model: deepseek-v4.1-flash  # the EDITOR: picks which items make the digest
  summarize_model: ""       # the WRITER: writes each summary ("" = same model)
```

Any OpenCode Console model id works — `glm-5.3`, `glm-5.3-flash` (cheaper writer),
`deepseek-v4.1-flash`, `kimi-k3`, `claude-sonnet-5-5`, `gpt-6.1-sol`, ...
Full list: https://opencode.ai/inference/v1/models
Default: `deepseek-v4.1-flash` for both roles (vision-capable, also reviews
article images). Any OpenCode Console model id works — `glm-5.3`,
`glm-5.3-flash` (cheaper writer), `deepseek-v4.1-flash`, `kimi-k3`,
`claude-sonnet-5-5`, `gpt-6.1-sol`, ...
Or switch without editing: `set DIGEST_LLM_MODEL=...` / `set DIGEST_LLM_SUMMARIZE_MODEL=...`.
Set `summarize: false` to skip the writer and show raw abstracts.
Pay-as-you-go key instead of Go? Also change `base_url` to `https://opencode.ai/inference`.

See the effective config anytime: `uv run daily-digest print-config`.

## Commands

| Command | What it does |
| --- | --- |
| `uv run daily-digest run` | Fetch → rank → digest → popup + toast (the daily job; idempotent per day) |
| `uv run daily-digest run --force` | Redo today even if already delivered |
| `uv run daily-digest run --no-notify` | Rebuild the digest without toast/popup (won't block the real one) |
| `uv run daily-digest run --date 2026-11-17` | Backfill a specific date |
| `uv run daily-digest smoke` | Live-check all sources, print counts |
| `uv run daily-digest notify-test` | Send a test toast that opens the digest |
| `uv run daily-digest print-config` | Show effective config (secrets redacted) |
| `uv run daily-digest open [latest\|YYYY-MM-DD]` | Open a digest manually (popup window; `--web` for browser) |
| `uv run daily-digest tray` | Run the tray app (normally started automatically at login) |
| `uv run daily-digest install-tray` | Desktop shortcut (Ctrl+Alt+D) + tray auto-start + launch tray now |
| `uv run daily-digest uninstall-tray` | Remove shortcuts, stop the tray app |
| `uv run daily-digest install-task` / `uninstall-task` | Manage the 09:00 scheduled task |
| `uv run pytest` | Full test suite (offline, mocked HTTP/LLM, no real desktop changes) |

## How it works

```
09:00 Task Scheduler (hidden pythonw, battery-safe, catches up when asleep)
  └─ fetch:  HN front page · HF Daily Papers · arXiv announcements (RSS, cs.CL/cs.LG/cs.AI)
             · Emergent Mind (trending on X/Reddit/YouTube) · alphaXiv (community upvotes,
             needs a free key in .env)   — 5 independent sources, keyless except alphaXiv
  └─ merge:  same paper from several sources → one item (provenance: HF > alphaXiv > EM > arXiv)
  └─ enrich: OpenAlex citation counts (keyless, one batched request) → "N citations" evidence
  └─ filter: skip items already shown in the last 7 days (state.json seen-set)
  └─ EDITOR LLM (deepseek-v4.1-flash): picks top ~12 + writes "why it matters"   ← heuristic fallback if down
  └─ WRITER LLM (summarize_model, same by default): writes a 2-3 sentence
     summary of every selected item                                  ← falls back to raw abstracts
  └─ render: output/digest-YYYY-MM-DD.html + latest.html — atomic writes
  └─ deliver, both channels:
       🪟 popup:  native window with the digest (runs detached, outlives the task)
       🔔 toast:  click → dailydigest:// → opens the popup window
```

- **Sources fail independently** — one site being down just shrinks that day's digest.
- **LLM fails** → heuristic ranking (keyword hits + points + recency); digest still arrives.
- **Everything is logged** to `logs/daily-digest.log` (rotating, 1 MB × 5).
- Exit codes: `0` clean · `1` degraded (check log) · `2` fatal.
- Old digests stay archived in `output/` — catch up on missed days anytime.

## Configuration

Everything lives in `config.yaml` (all optional; sensible defaults built in):

- `interests.topics` — what the ranker optimizes for
- `sources.*.enabled`, `sources.arxiv.categories` — add `cs.CV`, `stat.ML`, ...
- `llm.top_n` — digest size (default 12)
- `notify.popup` / `notify.enabled` — turn the popup/toast channels on/off
- `schedule.time` — when `install-task` schedules it (default 09:00)
- `state.seen_days` — how long an item is suppressed after appearing (default 7)

## Troubleshooting

- **No toast at 09:00** — check `Get-ScheduledTaskInfo 'Daily AI Digest'` and the log.
  The task runs on battery, catches up if the PC was asleep (`StartWhenAvailable`),
  and only fires while you're logged in (toasts need an interactive session).
- **Toast appears but click does nothing** — run `uv run daily-digest notify-test` and click;
  the log shows the `dailydigest://latest` launch URI. Also check Settings → System →
  Notifications (the toast arrives under Windows' "Command Prompt" app identity).
- **Do Not Disturb is on** — banners are suppressed, but the toast still lands in the
  Notification Center and the popup still opens.
- **"degraded" digest / exit code 1** — one source failed or the LLM was unreachable;
  the log says exactly which. Missing API key shows `heuristic (LLM offline)` in the digest.
- **LLM HTTP 401/403/404** — key wrong, or `base_url`/`model` don't match your plan
  (Go subscription → `/inference/go`; pay-as-you-go → `/inference`).

## Layout

```
daily-digest/
├─ daily_digest/          # the package (fetchers, rankers, render, notify, pipeline, cli)
├─ templates/digest.html.j2
├─ tests/                 # 53 tests, mocked HTTP + LLM (respx), no live calls
├─ config.example.yaml    # copy to config.yaml to customize
├─ .env                   # your API key (git-ignored)
├─ output/                # digest-YYYY-MM-DD.html + latest.html (git-ignored)
├─ logs/                  # daily-digest.log (git-ignored)
└─ state.json             # seen-set + per-day state (git-ignored)
```
