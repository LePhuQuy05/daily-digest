# Feature-ideas landscape — what comparable products offer

**Purpose:** external evidence for "what should we add next" to the personal Windows
daily-digest tool. Every claim below was verified against a primary source (official
site, docs, app-store listing, or GitHub repo API) on **2026-11-19**. Liveness is
stated as of that date. Dead/dormant products are marked but their ideas remain fair
game.

**Our stack assumptions for effort ratings** (Python, local, keyless-first):
pywebview popup with JS↔Python bridge, existing editor/writer LLM clients,
`state.json`, HTML archive by date, Task Scheduler, tray app, toast.

- **Effort:** trivial (<½ day) · small (1–2 days) · medium (3–7 days) · large (>1 week)
- **Fit:** adoptable (works local/keyless) · needs adaptation · not applicable (cloud/social-only)

---

## Summary table

| # | Feature idea | Source product(s) | Evidence it's valued | Fit | Effort |
|---|---|---|---|---|---|
| 1 | Keyword include/mute filters + per-source tuning | Inoreader rules/filters, Feedly AI prioritization | Core paid features of both readers for a decade | adoptable | small |
| 2 | Like/dislike feedback → personalized ranking ("For You") | alphaXiv For You feed; Feedly Leo; zotero-arxiv-daily (6.1k★); arxiv-sanity (5.8k★) | 6.1k-star hobby repo whose whole value is recommend-from-library | adoptable | medium (buttons alone: trivial) |
| 3 | On-demand "explain this item" (fetch paper → LLM Q&A) | alphaXiv AI overviews, SciSpace Chat-with-PDF, Emergent Mind grounded Q&A | Flagship feature of every research platform surveyed | adoptable | small–medium |
| 4 | Saved-items folder (read-later) with tags | Readwise Reader, Feedly boards, Zotero collections | Readwise: "power readers" pay $9.99/mo largely for this | adoptable | small |
| 5 | Spaced resurfacing of saved items ("second look" section) | Readwise Daily Review | Readwise's most-cited differentiator vs Pocket (which shut down) | adoptable | small–medium |
| 6 | Full-text search across all past digests | The Batch search, Feedly search, Readwise search | Standard on every archive-backed product | adoptable | trivial (SQLite FTS5 / Whoosh) |
| 7 | Audio version of the digest (offline Windows TTS) | SciSpace "Turn Paper to Podcast", researchpod.app, alphaXiv narration, Emergent Mind narrated videos | Whole paper-to-podcast product category emerged 2025–2026 | adoptable | small |
| 8 | Weekly / monthly recap edition | Hugging Face Daily Papers (Daily/Weekly/Monthly tabs), The Batch weekly | HF added weekly/monthly views on top of daily | adoptable | trivial |
| 9 | Related-papers / citation-graph expansion per item | SciSpace, Elicit, alphaXiv (all have related-papers) | Standard reader-assist feature; we already have OpenAlex | adoptable | small |
| 10 | Export item → Zotero / Obsidian markdown | Zotero connector API, Readwise→Obsidian/Notion exports | Zotero is the standard researcher library (open source, local API) | adoptable | trivial–small |
| 11 | Telegram delivery channel | arXiv_recbot (307★), Broletter, edge-ai-papers-bot, GSAbot | Multiple maintained hobby bots; but needs a bot token (not keyless) | needs adaptation (one secret) | small |
| 12 | Email digest delivery | zotero-arxiv-daily (email topic tag), HF Papers "get trending papers in your inbox", Ben's Bites/TLDR model | Email is the #1 channel every commercial digest uses | needs adaptation (SMTP creds) | small–medium |
| 13 | Follow-researcher / keyword monitors ("Routines") | Elicit Routines (Sep 2026), alphaXiv custom feeds + notifications, Inoreader monitoring | Elicit shipped it as a flagship release; alphaXiv v2 feature | adoptable | medium |
| 14 | Agent/CLI access to digest history (MCP server or CLI) | Readwise MCP + CLI, Elicit API+MCP, alphaXiv MCP (21 tools), Emergent Mind Agent Skills | Every 2026 release cycle added MCP; Readwise also ships a CLI | adoptable | small–medium |
| 15 | "Why you're seeing this" provenance line | TLDR/Batch curation model, Feedly AI "analyst stays in control" | We already have editor why-lines; extend with scores/sources | adoptable | trivial |

Not applicable (cloud/social-only, listed for completeness): multiplayer collaboration
(Elicit multiplayer, Zotero groups), community comments/discussions (alphaXiv, HF
Papers community tab), enterprise threat-intel graphs (Feedly TI), shared web
newsfeed with upvotes (Ben's Bites newsfeed, AlphaSignal upvotes).

---

## 1. AI/tech newsletters & digests

### TLDR (tldr.tech) — ALIVE, ~8M readers
Checked https://tldr.tech and https://tldr.tech/newsletters (2026-11-19; front-page
stories dated Nov 18, 2026).

- **Web archive of every issue** — full daily archive browsable per date at
  `/tech/archives`; "Join 8,000,000+ readers … for one daily email".
  Evidence: archive link is in the site header; longevity since 2018. **Fit:** we
  already archive HTML by date — closest analog already built; add an index page.
  **Effort:** trivial.
- **Vertical customization (12 newsletters)** — Tech, AI, InfoSec, Dev, Product,
  DevOps, Founders, Design, Marketing, Crypto, Fintech, IT, Data, Hardware.
  Evidence: https://tldr.tech/newsletters lists all; the model works because readers
  self-select topics. **Fit:** single user — equivalent is per-topic sections or a
  topic filter in our digest. **Effort:** small (topic tags + filter).
- **No search and no audio versions found on site** (checked 2026-11-19). The gap is
  notable: even the biggest newsletter has no personal search; our local archive
  search would leapfrog it.

### The Batch (DeepLearning.AI) — ALIVE, weekly
Checked https://www.deeplearning.ai/the-batch/ (2026-11-19; issue 379 dated Nov 13,
2026, 25 pages of back issues).

- **Search across all issues** — dedicated `/the-batch/search`. **Fit/effort:**
  adoptable/trivial (FTS over our archive).
- **Tag/topic browsing** (letters, Data Points, ML Research, Business, Science,
  Culture, Hardware, AI Careers) — every issue is tagged; navigation is by tag.
  **Fit:** adoptable; **effort:** small.
- **"Popular Articles" ranking** — a recency+popularity leaderboard on the landing
  page. **Fit:** our analog is a "most upvoted/liked across the week" section fed by
  our own like buttons. **Effort:** small (needs #2's buttons).
- **Weekly cadence with a letter framing the week** — Andrew Ng's letter gives a
  narrative arc over raw items. Our "Tổng hợp hôm nay" already does this daily; a
  weekly recap letter variant is trivial on top of existing archives.

### Ben's Bites — ALIVE, ~118k subscribers, twice-weekly
Checked https://www.bensbites.com/ and https://bensbites.co/ (2026-11-19; Substack
post dated 2026-11-17).

- **Full web archive** (Substack `/archive`) — every email is a permalinked web page;
  the newsletter and site are one artifact. Evidence: archive is public and linked.
  **Fit:** our HTML archive is the same pattern; **effort:** trivial (we have it).
- **Companion newsfeed where "best posts (+ our curated picks) get mentioned in the
  email digests"** (bensbites.co) — feed → digest funnel. **Fit/effort:** adoptable /
  medium (would need a feed-like staging area; low priority for single user).
- **Sessions/podcast feed** — their RSS carries a podcast namespace; they run
  interview sessions. Evidence of audio as a companion channel, not digest audio.

### AlphaSignal — ALIVE, pivoted newsletter → upvote news site
Checked https://alphasignal.ai/ (2026-11-19; items posted 1–20 h ago, 4,209 items in
last-24h filter; editorial team of 4 with a published newsroom policy).

- **"The Front Page of AI"**: LATEST/UPVOTES sort, topic filters, company pages, Pro
  (paid) tier — a Hacker-News-style layer over the newsletter.
  **Transferable idea:** *personal upvotes as a ranking signal*. For us: like buttons
  in the pywebview popup (JS→Python bridge writes to `state.json`), then a "your top
  of the week" view. **Effort:** trivial for the buttons; small for the ranked view.
- **Track "every model, repo, paper, and announcement in real time"** — their
  positioning. Confirms the multi-source daily-scan niche is commercially healthy.

---

## 2. Research-paper platforms

### alphaXiv — ALIVE (papers 1 day old; NeurIPS 2026 section; blog Sep 2026)
Checked https://alphaxiv.org/, its App Store / Google Play listings, and
https://alphaxiv.org/docs/mcp (2026-11-19).

- **For You feed** — personalized feed, exposed even in their MCP
  (`get_for_you_feed`). Evidence: top-level product surface + MCP tool. **Fit:**
  adoptable via like/dislike signals (#2). **Effort:** medium.
- **Custom feeds: create, follow, get notified** — app-store changelog: "Introducing
  Custom Feeds! Create, follow and get notified about new papers"; "Notifications
  for new papers from researchers and feeds you follow". **Fit:** needs adaptation —
  we'd implement as saved OpenAlex/arXiv author-or-keyword monitors. **Effort:**
  medium.
- **Library with folders, Liked, History** — "Redesigned Library with Publications,
  Liked and History"; "Bookmark favorite papers… organize your work"; MCP can query
  library folders. **Fit:** adoptable (local `state.json` + HTML archive).
  **Effort:** small.
- **2-minute explainer videos per paper + instant narration** — every paper card has
  "Watch explainer 2:00"; app: "Narration starts playing in about a second".
  **Fit:** audio idea #7; video out of scope. **Effort:** small (TTS).
- **Browser extension** ("alphaXiv: understand research papers"), **mobile apps**,
  **organization pages**, **AI Overviews** — cloud/mobile surfaces; not applicable
  to a Windows-local tool, but the extension pattern maps to our tray+popup.

### Emergent Mind — ALIVE as a "product lab"; assistant since 2022
Checked https://www.emergentmind.com/ and /about (2026-11-19; newest tool "Emergent
Mind Bot" dated 2026-11-08; "New ones ship most weeks").

- **AI Research Assistant: trending arXiv + grounded Q&A** — "Discover trending
  arXiv papers, read detailed summaries, and ask questions grounded in the
  research" (since 2022). This is the exact "ask questions about the digest" idea
  (#3). **Fit:** adoptable — on-demand LLM pass over item abstract/cached text.
  **Effort:** small–medium.
- **Open Problems** — 37K unsolved research questions extracted from arXiv papers,
  each linked to the papers that raise it. **Fit:** adoptable as a niche section for
  research-minded users; **effort:** medium (extraction pipeline); low priority.
- **Agent Skills (since 2026)** — "Skills that let your coding agent find trending
  papers, search arXiv, explore open research problems and publish findings", plus a
  public **API** (search arXiv/trending/open problems from your own code).
  **Transferable:** expose our digest to agents/CLI (#14). **Effort:** small–medium.
- **Bot that "picks the AI stories worth explaining, checks the sources, and posts
  narrated videos"** — evidence for curation + verification + narration as a
  pipeline; supports ideas #7 and #15.
- **Note:** no email digest and no Chrome extension are listed anywhere on the
  current site (nav, homepage, /about) — if they existed before, they are gone as of
  2026-11-19. The assistant itself is the product.

### SciSpace — ALIVE (2026-dated compare/help pages)
Checked scispace.com literature-review and comparison pages via search, plus its
help center (2026-11-19; direct homepage fetch is JS-only).

- **Chat with Paper (PDF)** + **line-by-line inline citations** — every plan tier
  includes "Chat with Paper PDFs"; "AI answers with citations". **Fit:** on-demand
  item deep-dive (#3). **Effort:** small–medium.
- **Extract data into comparison tables** — "Extract data from paper PDFs" /
  evidence-matrix workflows. **Fit:** adoptable for "compare today's picks side by
  side" table in the digest; **effort:** medium.
- **"Turn Paper to Podcast"** — documented feature in the Literature Review table
  view (official tutorial). Strongest single evidence for #7.
- **200M+ paper corpus, related-papers and "find similar"** — comparison tables
  market corpus size and similarity search. Supports #9 (we can do this with
  OpenAlex, already integrated).

### Elicit — ALIVE (7M+ researchers claim; release log to Sep 2026)
Checked https://elicit.com/ (2026-11-19).

- **Routines (Sep 30, 2026): "Research that keeps working"** — "Tell the Elicit
  Research Agent what to keep current. Routines find new evidence, update your work,
  and report back for your review." This is the commercial validation of our core
  concept — a standing keep-me-current job with a reviewable diff. **Fit:** we
  already are a routine; the delta is *user-defined monitors* (#13). **Effort:**
  medium.
- **Library as persistent, reusable evidence store** (Sep 17, 2026: "Library into a
  shared research hub") — save-found-things-organize-reuse. Supports #4.
- **API + MCP (Jul 15, 2026): "Powering autonomous research engines"** — supports
  #14.
- **Sentence-level citations on every AI claim** — their "How we're different"
  section. Supports #15 (provenance lines) and our why-lines.

---

## 3. RSS/readers — "keep up without drowning"

### Feedly — ALIVE (© 2026; News Reader / AI / TI / Market Intel products)
Checked https://feedly.com/news-reader and https://feedly.com/ai (2026-11-19).

- **Boards + save-for-later with highlights/notes** — "Add notes or highlight
  sentences, then save it to a personal Board." **Fit:** adoptable, small (#4).
- **Follow newsletters via a feed email address** — "Get newsletters delivered to
  Feedly", plus Google News keyword feeds. **Fit:** needs adaptation (we could poll
  a newsletter RSS mirror); low priority.
- **Feedly AI: prioritize/analyze across millions of sources** — "a collection of
  machine learning models that gathers, analyzes, and prioritizes information…
  You're in control"; "Speed up your research by 70%". The pitch is triage, not
  reading. **Fit:** adoptable — our editor LLM already prioritizes; the missing
  piece is *user* priority signals (#1 filters, #2 likes). **Effort:** small.
- **Search across all your sources** — first-class feature. Supports #6.

### Inoreader — ALIVE (© 2026 Innologica; case studies; Inoreader Intelligence)
Checked https://www.inoreader.com/ (2026-11-19).

- **Rules** — "You set the rules, Inoreader does the work": auto-tag/route/notify on
  incoming items. A user tweet quoted on the homepage calls rules "the best premium
  feature". **Fit:** adoptable — config-driven keyword rules applied pre-LLM to cut
  noise and boost keywords. **Effort:** small.
- **Monitoring feeds** — keyword/topic monitors across the web in 30 languages.
  Supports #13 (medium).
- **Inoreader Intelligence** — "summarize articles, ask questions, execute custom or
  predefined prompts, and generate reports from multiple articles at once."
  Multi-article summarization = our "Tổng hợp hôm nay" pattern; ask-questions = #3.
- **Newsletters-as-RSS, web feeds for sites without RSS, Telegram-channel
  monitoring** — evidence that (a) email channels are ingestible, (b) scraping
  fallbacks exist. Telegram-channel *reading* is another candidate source for us.

### Readwise Reader — ALIVE (ships "nearly every week"; changelog public)
Checked https://readwise.io/read (2026-11-19).

- **Highlighting + tagging as first-class annotation** — "annotations are the key to
  getting more out of what you read". Out of scope for a digest tool, but saved-item
  notes (#4) is the lightweight version.
- **Daily Review (spaced resurfacing)** — "resurfaces the right highlight at the
  right time via email or app", based on spaced repetition. The single most
  transferable idea from the reader category (#5): our digest could include a
  "nhìn lại" (look back) section resurfacing items the user saved/starred 3–7–30
  days ago and never opened. **Effort:** small–medium.
- **Ghostreader (LLM copilot on any document)** — #3 evidence.
- **Text-to-speech with natural voices** — #7 evidence; we can do offline SAPI TTS
  for keyless-first.
- **Exports to Obsidian/Notion/Logseq/Roam/Evernote + full export anytime** — "your
  reading always remains yours". Supports #10 and a general "export everything"
  principle we already follow with HTML archives.
- **Readwise MCP server + CLI** — "connects Claude, ChatGPT, Cursor… to your
  library… can even organize your documents" (#14 evidence).
- **Liveness note:** competitor Pocket has **shut down**; Readwise explicitly
  markets the import path ("accepts your Pocket export file"). Read-later demand
  didn't die with Pocket — it consolidated.

---

## 4. Read-later / reference — how researchers save and resurface

### Zotero — ALIVE (open source, nonprofit Digital Scholar; Windows/Linux/Mac/iOS/Android)
Checked https://www.zotero.org/ (2026-11-19).

- **Collect with a click (browser connector senses arXiv/JSTOR/etc.)** — Zotero
  auto-extracts metadata as you browse. **Fit:** adoptable — a "Save to Zotero"
  button in our popup can POST to Zotero's **local** connector API
  (`http://localhost:23119`, no key, no cloud) when Zotero is running; graceful
  degrade to a `.bib`/markdown file when not. **Effort:** trivial–small.
- **Collections, tags, saved searches** — "saved searches that automatically fill
  with relevant materials as you work". Saved searches over our archive = #6 with
  stored queries; trivial once FTS exists.
- **Sync/groups** — cloud; not applicable (we stay local).

### Obsidian/Notion export patterns
From Readwise's integration matrix (see §3) the pattern researchers actually use is:
highlights/items flow **automatically** into a folder in their vault/notes app as
markdown, keyed by source. **Fit:** adoptable — write the day's saved items as
markdown into a configured Obsidian vault folder (a local path; no API, no key);
Notion needs a cloud API → not applicable for keyless-first. **Effort:** trivial
(Obsidian), medium (Notion, skip).

---

## 5. Open-source daily-arXiv digest projects on GitHub

GitHub search API, queries "arxiv daily" (1,484 repos), "arxiv telegram bot" (46),
"arxiv-sanity" (65); checked 2026-11-19. Stars/dates from repo metadata.

| Repo | Stars | Last push | Status | What it proves people want |
|---|---|---|---|---|
| TideDra/zotero-arxiv-daily | 6,166 (5.4k forks) | 2026-11-01 | **active** | Daily arXiv recommendations **from your Zotero library**, email delivery, GitHub Actions. The single strongest hobby signal: recommendation-from-history + email is worth 6k stars. |
| dw-dengwei/daily-arXiv-ai-enhanced | 3,048 | 2026-09-08 | active-ish | Daily crawl + **AI summaries** + GitHub Pages site — i.e., our editor/writer pipeline as a public site. |
| Vincentqyw/cv-arxiv-daily | 1,520 | 2026-11-16 | active | Auto-updating **web page** digest (papers.vincentqin.tech) via GitHub Actions; web archive as the UI. |
| duanyytop/agents-radar | 1,165 | 2026-11-18 | very active (created 2026-02) | "Daily AI ecosystem digest from 10 sources (GitHub, ArXiv, HN, HuggingFace, Product Hunt, Dev.to, Lobste.rs). **Bilingual ZH/EN** reports" — nearly our exact concept, public web version. Validates multi-source + bilingual. |
| ziwenhahaha/daily-paper-reader | 979 | 2026-10-05 | active | arXiv/OpenReview recommendation platform + **paper Q&A** (chat over papers) + GitHub Pages. |
| deep-diver/paper-reviewer | 858 | 2025-02-20 | slowing | Auto-generate a **long-form review** from an arXiv paper → blog post; powers a HF Daily Papers review site. Evidence for on-demand deep-dive (#3) at "review" depth. |
| karpathy/arxiv-sanity-preserver | 5,813 | 2021-11-27 | **dormant** | The 2015 original: browse/search/filter + tag-to-recommend. 1.3k forks; the recommendation idea outlived the code. |
| karpathy/arxiv-sanity-lite | 1,724 | 2023-06-19 | **dormant** | "Tag papers of interest → recommendations of similar papers" (SVM over tf-idf). Simple local personalization is enough — no embeddings farm needed. |
| zhengzhugithub/CV-arXiv-Daily | 702 | 2019-08-17 | **dead** | Earliest CV-papers-daily repo; template forks kept the pattern alive. |

**Reading of the signals:** the pattern that repeatedly earns stars is
*automatic + personalized + web/email delivered*. The personalization variants
(Zotero-library recs, tag-based recs) out-star the plain-digest variants ~2:1.

---

## 6. Delivery channels — what channels people actually use

### Telegram bots (GitHub, checked 2026-11-19)

- **yuandong-tian/arXiv_recbot** — 307★, Python, pushed 2025-11 (maintained by a
  well-known ML researcher): personal Telegram bot that recommends arXiv papers.
  A "serious user" built his own rather than use a website — personal-channel
  delivery has real pull.
- **landigf/Broletter** (2026-03) — "reads arXiv every night and sends a
  **personalized science briefing** — tap-to-expand preview cards, Gemini-powered,
  ~5 cents per user/month. Built for grad students drowning in papers." Our exact
  concept, delivered via Telegram.
- **maderix/edge-ai-papers-bot** — fetches, summarizes, distributes Edge-AI papers
  to Telegram. **carlosparaciari/ArXivBot** (dormant 2021), **GSAbot** (Google
  Scholar + arXiv keyword alerts, dormant 2022), **nanoy42/arxiv-update-bot** —
  a long tail, mostly dormant, but the maintained ones cluster on:
  *push channel + personal filters + summaries*.
- **Inoreader monitors Telegram channels as sources** (§3) — Telegram works in both
  directions (source and sink).

**Fit:** adoptable but **not keyless** — needs one bot token + chat id stored in
config; degrades gracefully (bot is optional, digest still renders locally).
**Effort:** small (single-chat bot, markdown message, fire-and-forget).

### Email

- Every commercial digest in this survey is email-first (TLDR 8M, Ben's Bites 118k,
  The Batch, AlphaSignal) — the channel with the deepest proven habit.
- **Hugging Face Daily Papers added an email subscription** ("Get trending papers in
  your email inbox once a day!") — one of our own sources chose email as the
  delivery surface. Checked https://huggingface.co/papers 2026-11-19.
- **zotero-arxiv-daily** (6.1k★) ships email as its primary delivery.
- RSS readers treat newsletters as ingestible feeds (Feedly, Inoreader, Readwise
  Reader) — email output can be re-consumed by any reader later.

**Fit:** needs adaptation (SMTP creds; or use Gmail app-password; still local-sent).
**Effort:** small–medium (one HTML email template reusing the digest renderer).

### Also observed on HF Daily Papers (an existing source of ours)
Daily/Weekly/Monthly tabs (`/papers/trending`), per-day archives, upvote counts,
linked models/datasets/Spaces counts per paper, community thread counts, and
"Submitted by" attribution. Cheap, transferable: **weekly/monthly recap (#8)** and
**showing linked artifacts (models/datasets) per paper item** in our digest
(effort: small — OpenAlex + HF paper page already expose these).

---

## Most-transferable features (shortlist)

Ranked by (evidence strength × fit × payoff / effort) for a local single-user tool:

1. **Keyword include/mute rules + topic filter** (Inoreader/Feedly) — the
   "without drowning" half of the value proposition; small.
2. **Like/dislike buttons → weekly "your top picks" + personalized ranking** —
   start trivial (buttons + state), grow into ranking; the 6.1k-star
   zotero-arxiv-daily and alphaXiv's For You prove the pull.
3. **Saved-items folder with tags + "nhìn lại" spaced-resurfacing section**
   (Readwise Daily Review, Zotero collections) — turns a fire-and-forget digest
   into a memory; small.
4. **On-demand "explain / ask about this item"** in the popup (alphaXiv overviews,
   SciSpace chat-with-PDF, Emergent Mind Q&A) — the flagship feature of the whole
   research-platform category; small–medium, uses existing LLM clients.
5. **Full-text search + an archive index page** (The Batch search, Readwise) —
   trivial with SQLite FTS5 over the HTML archive we already keep.
6. **Audio edition via offline Windows TTS** (SciSpace paper-to-podcast,
   researchpod.app, alphaXiv narration) — keyless (SAPI/pyttsx3), small.
7. **Weekly/monthly recap editions** (HF Papers tabs, The Batch letter) — trivial
   aggregation over existing archives.
8. **Related papers / citations expansion per item** (OpenAlex already integrated;
   every platform surveyed has it) — small.
9. **Export: Zotero via local connector API (keyless), Obsidian folder as
   markdown** (Readwise export patterns) — trivial–small.
10. **Telegram and/or email delivery as optional channels** — one secret each,
    graceful degradation; evidence everywhere in §6.
11. **Follow-researcher / keyword monitors ("Routines", custom feeds)** — Elicit's
    Sep 2026 flagship; medium, the biggest step beyond current scope.
12. **Agent/CLI access to the digest archive (MCP server or plain CLI)** — the
    2026-wide pattern (Readwise MCP+CLI, Elicit MCP, alphaXiv MCP, Emergent Mind
    Agent Skills); small–medium, and a natural fit for a local tool.

Explicitly **not** worth copying for a single-user local tool: community
discussions/comments, upvote leaderboards fed by other people, multiplayer
libraries, enterprise intel graphs, and web-hosted public newsfeeds.

---

*All URLs cited above were fetched/searched on 2026-11-19. GitHub star and push-date
figures are from the GitHub REST search API on that date and will drift.*
