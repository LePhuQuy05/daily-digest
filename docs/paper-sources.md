# Paper-source catalog for daily-digest

**Researched: 2026-11-19.** Every "checked 2026-11-19" claim below was verified against the owning site on that date (fetched directly or probed with HTTP requests); anything not verifiable is explicitly marked as unverified. 2026 was a year in which several famous paper sites died or walled themselves off — Papers With Code is gone, and OpenReview and dblp both now sit behind anti-bot challenges — so re-verify this catalog quarterly.

**Context.** `daily-digest` fetches ~60–100 AI/ML items every morning from three keyless sources — Hacker News front page (Algolia API), Hugging Face Daily Papers (`huggingface.co/api/daily_papers`), and arXiv announcement RSS for cs.CL/cs.LG/cs.AI — merges by arXiv id, then an editor + writer LLM pair curates ~12 items for an AI engineer (LLMs, NLP, RL/agents, interpretability, ML broadly, AI engineering). Each source is a Python `fetch(client, cfg) -> list[Item]` where `Item = {id, title, url, source, points, published, summary}`; sources fail independently; keyless API/RSS access is strongly preferred. Sources that resurface the same arXiv papers with extra signal (upvotes, reviews, discussion) are high value because arXiv-id dedup already exists. All three current sources were confirmed live on 2026-11-19 (see "Current sources" at the end).

## Summary table

| Source | Verdict | Access | Auth | Marginal value over current 3 sources |
| --- | --- | --- | --- | --- |
| Emergent Mind | **ADD-NOW** | RSS (keyless, live) + JSON API | RSS keyless; API free key (50 req/mo) | Same arXiv papers + cross-platform social attention (X/HN/Reddit/YouTube) |
| alphaXiv | OPTIONAL | Official MCP server (streamable HTTP); no RSS | Free API key / OAuth | Same arXiv papers + upvotes & discussion ("hot" feed) |
| Semantic Scholar (Ai2) | OPTIONAL | REST (Graph / Recommendations / Datasets) | Keyless (shared pool, 429-prone) or free key (1 RPS) | Not a feed — enrichment: citation & influential-citation counts for merged items |
| OpenReview | OPTIONAL (blocked) | REST API v2 + `openreview-py` | Free account | Would add peer-review ratings/discussion; **challenge-blocked as of 2026-11-19** |
| papers.cool | OPTIONAL | Atom feeds per arXiv category (keyless, live) | Keyless | None for new papers (mirrors arXiv); cleaner feeds + venue browsing + more categories |
| OpenAlex | OPTIONAL | REST (`api.openalex.org`) | Keyless (10 rps/IP) or free key | Enrichment alternative to S2 (citations, topics); not a feed |
| SciRate | SKIP | Website only; 403 to non-browser clients (observed) | n/a | Scite-upvote signal would be nice, but unreachable programmatically |
| dblp | SKIP | XML API + dumps — behind Anubis challenge (observed) | n/a | Low anyway: venue metadata, no ranking, duplicates arXiv |
| Google Scholar | SKIP | No API; ToS prohibits robots.txt-violating automation | n/a | Citation data obtainable legitimately via S2/OpenAlex |
| Connected Papers | SKIP | Web app; no public API documented | Paid tiers | Discovery-from-a-seed, not a daily feed |
| ResearchRabbit | SKIP | Web app; no public API documented | Free account | Discovery/mapping tool, not a feed |
| Inciteful | SKIP | Web app; community MCP; no public REST API | Free | Citation-graph discovery tool, not a feed |
| arXiv Sanity Lite | SKIP | Site unreachable (observed); self-hostable app | n/a | Dormant since 2023; no hosted feed |
| ar5iv | SKIP | HTML renderings of arXiv papers | Keyless | Reading aid, lags ~1 month, not a feed |
| bioRxiv / MedRxiv | SKIP (out of scope) | Documented keyless API (`api.biorxiv.org`) | Keyless | Biology/medicine preprints; irrelevant unless digest expands to AI-for-bio |
| The Batch | SKIP | Newsletter website | Email signup | Human-written weekly editorial, not a paper website |
| TLDR | SKIP | Newsletter website | Email signup | `tldr.tech/papers` is 404; newsletters are general tech news |
| FutureHouse | SKIP | Own research blog | n/a | A lab's publication feed, not a broad paper source |
| **Papers With Code** | **DEAD** | `paperswithcode.com` now serves Hugging Face | — | Shut down July 2025; see obituary |

---

## ADD-NOW candidates

### Emergent Mind — emergentmind.com

1. **What / who runs it.** An arXiv paper tracker and "AI Product Lab" built by indie developer Matt Mazur; the AI research assistant has been running "since 2022" and the site now also offers Open Problems (37K extracted from arXiv papers), an email digest, a Chrome extension, and agent skills. Solo-maintainer project — treat as a bus-factor risk. (https://www.emergentmind.com/, checked 2026-11-19)
2. **Coverage & focus.** All of arXiv (observed feed items included astrophysics, quantum and math papers alongside ML — filtering needed). Each paper is enriched with aggregated social signals: X/Twitter likes, Hacker News points, Reddit points, YouTube mentions, plus citation counts. (API docs: https://www.emergentmind.com/docs/api, checked 2026-11-19)
3. **Update cadence.** Continuous, per-paper: items appear as papers gain attention (feed `pubDate`s observed Nov 11–17, 2026). The API's `trending` endpoint ranks everything published in a date window (default: last 7 days) by accumulated attention.
4. **Access method.** Two routes, both verified live:
   - Keyless RSS 2.0: `https://www.emergentmind.com/feeds/rss` — "Trending arXiv papers, explained by GPT-4"; items carry title, abstract, arXiv link, pubDate (fetched 2026-11-19, items present).
   - JSON API: base `https://api.emergentmind.com` — `POST /v1/papers/trending` (rank by attention, filter by arXiv categories, up to 50 results), `POST /v1/papers/search`, `GET /v1/papers/{arxiv_paper_id}`; machine-readable OpenAPI 3.1 spec at `/docs/api/openapi.json`. (https://www.emergentmind.com/docs/api, checked 2026-11-19)
5. **Auth.** RSS: keyless. API: key required (`x-api-key` header), free plan includes 50 API requests/calendar month (Pro 2,500; Max 10,000). One trending call per day fits the free tier.
6. **Rate limits.** Monthly request quota by plan; every response carries `X-RateLimit-*` headers; over-quota returns 429 with `quota_exceeded`. (API docs, checked 2026-11-19)
7. **Marginal value.** High: the same arXiv papers our arXiv/HF sources already see, but ranked by *cross-platform* social attention — a signal none of the current three sources capture (HF Daily Papers' upvotes come only from the HF community). Caveats: the RSS feed is subject-unfiltered; citation counts are `citations_count: 0` with `citations_checked: false` for most papers (the docs themselves say counts are polled only for a slice of arXiv — don't trust the zero).
8. **Verdict: ADD-NOW** — keyless RSS + high signal, with an optional free-key upgrade for category-filtered trending with numeric social signals.

### (Runner-up ADD-NOW) Semantic Scholar batch enrichment is the strongest *optional* second step — see its section; the reason it is not ADD-NOW is that it adds enrichment, not new items, and keyless use is 429-prone.

## OPTIONAL candidates

### alphaXiv — alphaxiv.org

1. **What / who runs it.** A startup-run platform to "follow the latest research": arXiv papers with community upvotes, researcher profiles, organization pages, AI-generated explainers, and conference hubs (e.g. NeurIPS 2026). Feedback goes through `github.com/alphaxiv/feedback`. Site live with fresh content (papers from ~1 day ago with upvotes shown). (https://alphaxiv.org/, checked 2026-11-19)
2. **Coverage & focus.** All of arXiv with an AI/ML-heavy community; the front page is effectively a trending feed (upvotes + views per paper).
3. **Update cadence.** Continuous; the documented "Hot feed" covers papers hot over the last 30 days.
4. **Access method.** Official **MCP server** at `https://api.alphaxiv.org/mcp/v1` (Streamable HTTP; POST/GET-SSE/DELETE). Relevant tools: `get_hot_feed` (the app's unfiltered Hot feed over 30 days, returns ordered `universal_paper_id` = arXiv ids, limit 1–200) and `get_for_you_feed`; feed retrieval "makes no model calls and does not consume assistant quota or record impressions". Browser-hosted MCP is not supported (CORS locked) — use a native MCP client or a local bridge. No RSS (`alphaxiv.org/rss` → 301, no feed; checked 2026-11-19). Community SDKs (e.g. `petroslamb/alphaxiv-py`) also drive an **undocumented** REST surface on `api.alphaxiv.org` (dev docs at `api-dev.alphaxiv.org`) — unverified, no published contract, avoid depending on it. (MCP docs: https://alphaxiv.org/docs/mcp, checked 2026-11-19)
5. **Auth.** OAuth 2.1 browser flow by default, or a **free API key** (Settings → API Keys) sent as `Authorization: Bearer <key>`, which skips OAuth for scripts. Not keyless.
6. **Rate limits.** Feed tools are free of assistant quota; the search/analysis tools count against it. No numeric rate limits published for the feed tools in the MCP docs.
7. **Marginal value.** Good: same arXiv papers plus upvote/discussion signal — a different crowd than HF's upvoters. Returns ids only, so titles/abstracts must come from our existing pipeline items or the arXiv API.
8. **Verdict: OPTIONAL** — free key + MCP transport (not plain REST, not keyless) buys a solid second popularity signal.

### Semantic Scholar (Ai2) — semanticscholar.org

1. **What / who runs it.** Semantic Scholar, the open scholarly data platform of the Allen Institute for AI (Ai2); ~214M papers, 2.49B citations, 79M authors; has an API status page (status.api.semanticscholar.org). (https://www.semanticscholar.org/product/api, checked 2026-11-19)
2. **Coverage & focus.** All scientific fields (not ML-specific); arXiv is indexed promptly; per-paper metadata includes citationCount, influentialCitationCount, fieldsOfStudy, open-access PDF links, SPECTER2 embeddings.
3. **Update cadence.** Continuously updated corpus; snapshot dataset releases (latest release observed: 2026-11-10).
4. **Access method.** Three REST services (all verified live 2026-11-19):
   - Academic Graph: `https://api.semanticscholar.org/graph/v1` — relevance search, bulk search (`/paper/search/bulk`, supports `publicationDateOrYear`, sort by citationCount), `GET /paper/{id}` (accepts `ArXiv:2611.23144`-style ids), `POST /paper/batch` (up to 500 ids in one call — ideal for enrichment).
   - Recommendations: `https://api.semanticscholar.org/recommendations/v1` — `GET /papers/forpaper/{paper_id}` (verified: HTTP 200 keyless) and `POST /papers` with `positivePaperIds`/`negativePaperIds`.
   - Datasets: `https://api.semanticscholar.org/datasets/v1` — release listing keyless (verified), download links require a key.
   (Tutorial with all endpoints and Python examples: https://www.semanticscholar.org/product/api/tutorial, checked 2026-11-19)
5. **Auth.** Most endpoints work keyless but share one pool across *all* unauthenticated users; a **free API key** (email request form) gives a dedicated 1 req/sec across all endpoints and is officially recommended.
6. **Rate limits.** API page: unauthenticated traffic is "rate-limited to 1000 requests per second shared among all unauthenticated users" and "may also be further throttled during periods of heavy use" — in practice our keyless test calls were 429'd twice on 2026-11-19, so treat keyless as unreliable for anything bursty. Keyed introductory limit: 1 RPS (possibly raised after review). (https://www.semanticscholar.org/product/api#api-key, checked 2026-11-19)
7. **Marginal value.** As a discovery feed: none (no trending endpoint is documented). As an **enrichment pass**: high — one `POST /graph/v1/paper/batch` call per day can stamp citation and influential-citation counts onto every merged item, giving the editor LLM an "established vs brand-new" signal. The recommendations API could optionally pull "papers similar to yesterday's top picks".
8. **Verdict: OPTIONAL** — free key, 1 RPS is plenty for one daily batch; use the batch endpoint to stay under limits.

### OpenReview — openreview.net

1. **What / who runs it.** OpenReview, the open peer-review and publishing platform used by major ML conferences (its docs host e.g. NeurIPS 2021 and ECCV 2020 conference reports). Documentation at docs.openreview.net (GitBook, actively maintained). (https://docs.openreview.net/, https://docs.openreview.net/reports/conferences/openreview-neurips-2021-summary-report.md, checked 2026-11-19)
2. **Coverage & focus.** Venue submission records plus reviews, ratings, meta-reviews and author discussion for NeurIPS/ICLR/ICML-class venues — i.e., exactly the peer-review signal no other source in this catalog has.
3. **Update cadence.** Seasonal, tied to conference cycles (submissions → discussion → decisions), not daily.
4. **Access method.** REST API v2 at `api2.openreview.net` with a published OpenAPI spec (`https://api2.openreview.net/docs/api.yml` — served fine, HTTP 200, checked 2026-11-19) and an official Python client (`pip install openreview-py`). Queries go by invitation / `content.venueid`. **Blocker observed:** on 2026-11-19 every *data* query we tried returned HTTP 403 `ChallengeRequiredError` ("Challenge verification required", with a `challengeUrl` at openreview.net/challenge) — for a raw `curl` with a browser User-Agent *and* for `openreview-py` guest-mode `get_all_notes` (error reproduced with the official client, Python 3.11, openreview-py installed from PyPI). Static assets are unaffected; the challenge appears to gate note retrieval. This looks like recent anti-bot protection; no official announcement about it was found in the docs we fetched.
5. **Auth.** Free OpenReview account (username/password; MFA supported with a documented unattended-script flow). Guest access for public notes is the documented default in the client — currently blocked by the challenge described above.
6. **Rate limits.** Could not be verified — the challenge prevented reaching the data endpoints, and the docs pages fetched do not state numeric limits.
7. **Marginal value.** Potentially high but seasonal: ratings/review-discussion for fresh submissions (e.g. ICLR season) would let the digest say "community reviews rate this 6/10". Not a daily-new-papers source, and presently unreachable from scripts.
8. **Verdict: OPTIONAL — do not build on it now.** Re-test quarterly; if the challenge is lifted, a `venueid`-filtered fetcher for active venues' submissions with ratings would be the integration.

### papers.cool — papers.cool

1. **What / who runs it.** "Cool Papers — Immersive Paper Discovery," a one-maintainer site by GitHub user `bojone` — verified to be 苏剑林 / Jianlin Su, a well-known NLP researcher (blog kexue.fm; ~12.9k GitHub followers; GitHub account since 2014). Repo created 2024-01-02, last push 2026-07-06, 821 stars; the site is serving November 2026 data, so it is actively maintained. (https://papers.cool/; https://github.com/bojone/papers.cool; https://api.github.com/users/bojone — all checked 2026-11-19)
2. **Coverage & focus.** Every arXiv category, plus manually curated conference venue pages (NeurIPS, ICLR, ICML, ACL, EMNLP, CVPR, … with per-track groupings; errors reportable on GitHub). Onsite search built on tantivy.
3. **Update cadence.** Mirrors official arXiv announcements with "delay usually not exceeding 10 minutes"; refreshed around 10:00 Beijing time on weekdays, **no updates on weekends** (site's own note, checked 2026-11-19).
4. **Access method.** Keyless Atom feeds per category: `https://papers.cool/arxiv/{category}/feed` (verified live for cs.LG — full abstracts, authors, arXiv ids, updated timestamps; also `https://papers.cool/venue/latest/feed` → HTTP 200). Plus HTML day/category/venue pages.
5. **Auth.** Keyless.
6. **Rate limits.** None published (personal site — be gentle; one fetch per morning is fine).
7. **Marginal value.** Low as a *new-item* source: it is the same arXiv new-arrival stream our arXiv RSS already ingests, with no ranking/trending signal. Where it helps: (a) a cleaner alternative feed (well-formed Atom with full abstracts, no arXiv RSS quirks), (b) a trivial way to extend category coverage (stat.ML, cs.NE, cs.RO, eess.AS…), (c) venue/proceedings browsing. Bus factor: one maintainer.
8. **Verdict: OPTIONAL** — adopt as an arXiv-feed upgrade/extension only; note that adding the corresponding `export.arxiv.org/rss/{cat}` feeds directly achieves the same coverage with zero new dependencies.

### OpenAlex — openalex.org

1. **What / who runs it.** OpenAlex, the fully-open scholarly metadata catalog (the community successor to Microsoft Academic Graph); docs at docs.openalex.org (page last updated November 17, 2026). (https://docs.openalex.org/how-to-use-the-api/rate-limits-and-authentication, checked 2026-11-19)
2. **Coverage & focus.** All fields; works records include arXiv ids/DOIs, citation counts, topics/concepts.
3. **Update cadence.** Continuously updated; new works appear within days.
4. **Access method.** Plain REST at `api.openalex.org/works` with rich filters (e.g. `from_publication_date`); `select=` fields; batch OR-id lookups (up to 100 per filter).
5. **Auth.** Keyless works (limits counted per IP); a free API key (email-verified) raises the budget 10× and is required for cursor paging past page 1.
6. **Rate limits.** Keyless: 10 requests/second per IP (reduced from 100 rps on 27 June 2026); free key: 30 rps with a $1/day value budget (list calls $0.0001, searches $0.001); 429s carry `reason` + `Retry-After`. (docs page, checked 2026-11-19)
7. **Marginal value.** Enrichment only — same role as Semantic Scholar (citation counts, topics) with more generous limits; not a curated or trending feed.
8. **Verdict: OPTIONAL** — a good S2 fallback if S2's 429s annoy, but pick one enrichment provider, not both.

## SKIP candidates

### SciRate — scirate.com

1. **What / who runs it.** Open-source (Ruby, MIT) arXiv rating & commenting community site — papers are upvoted ("scited") and discussed; GitHub org active (repo last push 2026-09-14). (https://github.com/scirate/scirate and its README, checked 2026-11-19)
2. **Coverage & focus.** All arXiv; the sciting community skews heavily to quant-ph (this week's top papers observed via search results were quantum papers).
3. **Update cadence.** Per arXiv announcement (their About page notes they lag the arXiv API by hours).
4. **Access method.** Website only. **Observed:** `scirate.com` and `scirate.com/arxiv/cs.LG` both returned HTTP 403 on 2026-11-19 — via the fetch tool and via `curl` with a browser User-Agent. No documented public API (the repo README is development setup only). Site content itself is alive (search results show papers scited Nov 13–18, 2026) — it is specifically non-browser clients being refused.
5. **Auth.** n/a.
6. **Rate limits.** n/a (blocked before any request is served).
7. **Marginal value.** Would be an upvote signal (like alphaXiv's, smaller community); unreachable from our kind of tool, and thin in cs.CL/cs.LG relative to quant-ph.
8. **Verdict: SKIP** — alive for humans, walled for scripts, no API. Revisit only if they publish an API or the 403 lifts.

### dblp — dblp.org

1. **What / who runs it.** dblp, the long-running CS bibliography operated by Schloss Dagstuhl (operator attribution from long-standing public record — dblp.org itself sat behind an anti-bot challenge when checked, so on-site attribution could not be re-verified).
2. **Coverage & focus.** All of CS; indexes published venues and mirrors arXiv; bibliographic metadata only — no ranking, no social signal.
3. **Update cadence.** Frequent record updates; not a morning-announcement stream.
4. **Access method.** Documented XML API (`dblp.org/search/publ/api`) and XML dumps. **Observed 2026-11-19:** both the FAQ page and the search API endpoint returned an **Anubis proof-of-work challenge** (Anubis v1.27.0 interstitial — the anti-AI-scraper tool). A plain Python fetcher cannot pass it.
5. **Auth.** None for content (when not walled).
6. **Rate limits.** Previously documented courtesies; could not re-verify behind the wall.
7. **Marginal value.** Low even if accessible: duplicates papers we already get from arXiv, adds venue metadata, no selection signal for curation.
8. **Verdict: SKIP** (anti-bot wall + low marginal value).

### Google Scholar — scholar.google.com

1. **What / who runs it.** Google LLC. (https://scholar.google.com, checked 2026-11-19)
2. **Coverage & focus.** Everything; strongest citation coverage.
3. **Update cadence.** Continuous crawl.
4. **Access method.** Website only. **No official API exists or is documented** on any Google/ Scholar page we could find (checked 2026-11-19).
5. **Auth.** n/a.
6. **Rate limits.** n/a — Scholar is famous for rate-limiting/CAPTCHA-ing automated traffic.
7. **Marginal value.** Citation counts — which we can get legitimately from Semantic Scholar or OpenAlex.
8. **Verdict: SKIP.** The Google Terms of Service (effective July 30, 2026) prohibit "using automated means to access content from any of our services in violation of the machine-readable instructions on our web pages (for example, robots.txt files that disallow crawling…)" (https://policies.google.com/terms, checked 2026-11-19). No API + ToS hostility + bot-blocking = no compliant keyless route.

### Connected Papers — connectedpapers.com

1. **What / who runs it.** A paper-discovery web app that draws a citation-graph "similar papers" map; it is built on Semantic Scholar's corpus and APIs — S2's own API page carries their testimonial: "Since day 1 Connected Papers has been built on top of the Semantic Scholar Open Corpus and APIs." (https://www.connectedpapers.com/, https://www.semanticscholar.org/product/api — both checked 2026-11-19; the CP site is a JS app and returned no readable HTML)
2. **Coverage & focus.** All scholarly; discovery from a seed paper.
3. **Update cadence.** Live queries, not a stream.
4. **Access method.** Web app; no public API documented on the site (checked 2026-11-19).
5. **Auth.** Account; paid tiers for volume.
6. **Rate limits.** n/a.
7. **Marginal value.** None for a daily digest — it answers "what's around this paper?", not "what's new?".
8. **Verdict: SKIP** (discovery tool, no feed/API).

### ResearchRabbit — researchrabbit.ai

1. **What / who runs it.** Litmap Limited (2016–2026); literature-review mapping app trusted by many universities. (https://www.researchrabbit.ai/, checked 2026-11-19)
2. **Coverage & focus.** 320M+ papers; citation/co-authorship graph exploration and recommendations.
3. **Update cadence.** Live queries.
4. **Access method.** Web app (login); no public API documented (checked 2026-11-19).
5. **Auth.** Free account.
6. **Rate limits.** n/a.
7. **Marginal value.** None for a daily feed — same "discovery, not stream" category as Connected Papers.
8. **Verdict: SKIP.**

### Inciteful — inciteful.xyz

1. **What / who runs it.** Free citation-network tools ("Paper Discovery" + "Literature Connector"); GitHub org `inciteful-xyz` with public docs and a ChatGPT plugin/MCP. (https://inciteful.xyz/ checked 2026-11-19 — SPA; https://github.com/inciteful-xyz)
2. **Coverage & focus.** All scholarly; citation-network analysis from seed papers.
3. **Update cadence.** Live queries.
4. **Access method.** Web app; third-party API catalogues report no public REST API; an MCP server exists for citation-graph questions. Not a stream.
5. **Auth.** Free.
6. **Rate limits.** n/a.
7. **Marginal value.** None for a daily feed.
8. **Verdict: SKIP.**

### arXiv Sanity Lite — arxiv-sanity-lite.com

1. **What / who runs it.** Andrej Karpathy's self-hostable arXiv recommender (tag papers, get tfidf/SVM-based recommendations, optional daily emails). (https://github.com/karpathy/arxiv-sanity-lite, checked 2026-11-19)
2. **Coverage & focus.** arXiv ML/AI.
3. **Update cadence.** Was: polls the arXiv API on a cron.
4. **Access method.** Self-hostable Flask app; the hosted instance `arxiv-sanity-lite.com` failed to respond at all on 2026-11-19 (transport error). No public API.
5. **Auth.** n/a.
6. **Rate limits.** n/a.
7. **Marginal value.** None now: the repo's last push was **2023-06-19** (GitHub API, checked 2026-11-19) — the project is dormant and the hosted site is unreachable.
8. **Verdict: SKIP** (effectively dead as a hosted service; you could self-host it, but that's a different project).

### ar5iv — ar5iv.labs.arxiv.org

1. **What / who runs it.** An arXiv Labs project (Deyan Ginev / KWARC) rendering arXiv TeX to HTML5 via LaTeXML. (https://ar5iv.labs.arxiv.org/, checked 2026-11-19)
2. **Coverage & focus.** arXiv papers as readable HTML — a reading layer, not an index.
3. **Update cadence.** "Sources upto the end of October 2026. Not a live preview service" (site's own note, checked 2026-11-19) — roughly a month behind.
4. **Access method.** URL pattern (`ar5iv.org/abs/{id}`); no feed.
5. **Auth.** Keyless.
6. **Rate limits.** n/a.
7. **Marginal value.** None for discovery; useful for full-text reading of digest picks.
8. **Verdict: SKIP** as a source (keep the URL trick in mind for the writer).

### bioRxiv / MedRxiv

1. **What / who runs it.** Cold Spring Harbor Laboratory preprint servers for biology/medicine.
2. **Coverage & focus.** Biology/medicine preprints — out of scope for an AI engineer's digest (relevant only if it grows an AI-for-bio section).
3. **Update cadence.** Daily announcements.
4. **Access method.** Documented keyless API at `https://api.biorxiv.org` (details/content endpoints; page confirmed live 2026-11-19). MedRxiv served by the same API.
5. **Auth.** Keyless.
6. **Rate limits.** Pace-limited per their docs page (not re-verified in detail — out of scope).
7. **Marginal value.** None for the current digest profile.
8. **Verdict: SKIP (out of scope).**

### Newsletters & lab blogs (not paper websites — noted for completeness)

- **The Batch** (https://www.deeplearning.ai/the-batch/, checked 2026-11-19): DeepLearning.AI's weekly newsletter by Andrew Ng; latest issue Nov 13, 2026; includes an "ML Research" tag. Human-written editorial with a weekly cadence; no structured paper feed. Not a paper website — SKIP.
- **TLDR** (https://tldr.tech, checked 2026-11-19): daily tech newsletters (8M+ readers). **"TLDR Papers" does not exist** — `tldr.tech/papers` returns 404 (checked 2026-11-19). Their newsletters are general tech/AI news, not a paper source. SKIP.
- **FutureHouse** (https://futurehouse.org, checked 2026-11-19): nonprofit building AI agents for scientific discovery; publishes its own research announcements (Robin, DISCO, OXtal). A single lab's blog, not a broad feed. SKIP.
- **"NAS"** from the research brief is ambiguous — if it means **NASA ADS** (the astrophysics literature search service), that is out of scope for an AI engineer and its API status was not verified here; no credible AI/ML paper source matching "NAS" was identified.

---

## Obituary: Papers With Code (DEAD July 2025)

**What it was.** Papers With Code was *the* canonical index linking papers ↔ official code ↔ evaluation tables/SOTA leaderboards (hosted with Meta's support), routinely used to find implementations and benchmark standings.

**What happened.** The site went dark and began redirecting on **July 24–25, 2025** (date per multiple independent records: casrai.org guide, TIB library blog, MMRS record — all secondary). Primary evidence gathered 2026-11-19:

- `paperswithcode.com` now serves **Hugging Face's Trending Papers** page (verified by fetching the domain — HF content returned).
- GitHub issue [`paperswithcode/paperswithcode-data#116`](https://github.com/paperswithcode/paperswithcode-data/issues/116) ("https://paperswithcode.com now redirects to huggingface", opened Aug 14, 2025; fetched 2026-11-19) documents the shutdown. In it, **Julien Chaumond (julien-c), Hugging Face co-founder and CTO, confirms** (comment dated Sep 4, 2025): *"Our Trending papers section is only a partial alternative to PWC but one that some community members have found useful, so we chimed in and proposed Meta to redirect to it (instead of just killing the domain name)."* The public announcement was his X post of July 25, 2025 (x.com/julien_c/status/1948718297194561956, referenced in the issue).
- Follow-up (same issue, Dec 2025): HF set up per-paper and per-dataset redirects, e.g. `paperswithcode.com/paper/{slug}` → `huggingface.co/papers/{arxiv_id}`.

**What happened to its data.**
- Historical data dumps remain in [`github.com/paperswithcode/paperswithcode-data`](https://github.com/paperswithcode/paperswithcode-data) (the issue above lives there; repo still up, checked 2026-11-19).
- HF open-sourced the PWC code under **Apache-2.0** at [`github.com/huggingface/paperswithcode`](https://github.com/huggingface/paperswithcode) (LICENSE added October 2026), describing a rebuilt catalog of arXiv papers with code, datasets, leaderboards and Spaces — i.e., a partial revival is in progress on HF's side.
- Community clones sprang up in the same issue — SOTAPapers (sotapapers.com) and scholarwiki.ai — both unverified for trust/longevity; treat with caution.

**Verdict: DEAD — do not integrate.** The "trending papers + code links" role is partly covered by the already-integrated HF Daily Papers; GitHub stars are visible on HF paper pages as a code-signal proxy.

---

## Current sources status (all verified live 2026-11-19)

- **HN Algolia**: `https://hn.algolia.com/api/v1/search?tags=front_page` → HTTP 200, results returned.
- **HF Daily Papers**: `https://huggingface.co/api/daily_papers` → HTTP 200, JSON with current papers (e.g. 2611.21925); the papers page is "Trending Papers by AK and the research community" with daily/weekly/monthly views.
- **arXiv RSS**: `https://export.arxiv.org/rss/cs.LG` → HTTP 200, ~619 KB feed.

---

## Recommended integration order for daily-digest

1. **Emergent Mind — add now as two-stage (RSS today, API trending when a free key is acceptable).**
   - *Signal added:* cross-platform attention (X likes, HN points, Reddit points, YouTube mentions) on the same arXiv ids — complements HF's internal upvotes and HN's front page.
   - *Stage 1 (keyless):* fetch `https://www.emergentmind.com/feeds/rss` each morning. Parse the arXiv id out of the CDATA description (regex on `arxiv.org/abs/<id>`); the item `<link>` is a search URL, not a canonical paper URL, so prefer the arXiv id. Set `source="emergentmind"`, `points=None` (the feed has no numbers), `published=<pubDate>` (note: that's when EM surfaced it, not the paper's publication date — harmless given arXiv-id dedup).
   - *Gotchas:* the feed is subject-unfiltered (astro/quantum/math observed) — either drop items whose categories aren't AI/ML (one arXiv metadata lookup per new id, or let the editor LLM filter) or accept the noise and let the editor cut it; a solo-maintained site, so make the fetcher fail-soft.
   - *Stage 2 (free key, 50 req/month):* one `POST /v1/papers/trending` per day with `categories=["cs.AI","cs.CL","cs.LG","stat.ML"]`, `start_date`=yesterday — returns numeric `twitter_likes_count`, `hacker_news_points_count`, `reddit_points_points_count`… map `points = twitter_likes_count + hacker_news_points_count`. Watch `X-RateLimit-Remaining`; one call/day ≈ 30/month, safely inside 50.
2. **alphaXiv hot feed — second (free key + MCP).**
   - *Signal added:* upvotes and discussion from the researcher community on arXiv papers ("Hot" over 30 days).
   - *Gotchas:* requires creating a free API key and speaking MCP over streamable HTTP (`POST https://api.alphaxiv.org/mcp/v1`, `Authorization: Bearer <key>`) — a small MCP client in the fetcher, not plain REST; `get_hot_feed` returns **only ordered arXiv ids**, so hydrate titles/summaries from already-merged items (arXiv-id dedup covers the rest); the 30-day hot window means papers repeat across days — store per-day upvote snapshots if you want a "rising" signal; feed calls don't consume assistant quota.
3. **Semantic Scholar batch enrichment — third (free key).**
   - *Signal added:* `citationCount` + `influentialCitationCount` for every merged item → the editor LLM can weigh "already-influential" vs "brand-new"; optionally `fieldsOfStudy` for filtering.
   - *Gotchas:* request the free key via the email form (keyless use hits a saturated shared pool — we got 429s on 2026-11-19); 1 RPS keyed limit is fine for one daily `POST /graph/v1/paper/batch` (up to 500 ids, `ArXiv:` prefix, `fields=citationCount,influentialCitationCount,fieldsOfStudy`); keep a fallback to OpenAlex if S2 429s.
4. **Monitor, don't build:**
   - **OpenReview** — high-value review/rating signal, but data endpoints were challenge-blocked on 2026-11-19 for both raw HTTP and `openreview-py` guest queries. Re-test quarterly (especially around ICLR/NeurIPS submission seasons); if it opens up, fetch by `content.venueid` for active venues.
   - **papers.cool** — only if you want its cleaner Atom feeds or venue pages; otherwise adding `export.arxiv.org/rss/stat.ML`, `cs.NE`, `cs.RO` directly is the same content with zero new dependencies (and is the cheapest coverage win of all).

**General integration notes.** Normalize every external id to the bare arXiv id (strip `ArXiv:` prefixes, version suffixes `vN`, and URL paths) before dedup — Emergent Mind gives `2611.14996`, S2 wants `ArXiv:2611.14996`, alphaXiv uses "universal ids" that are the bare arXiv id. Rate-limit reality on 2026-11-19: S2 keyless 429-prone (get the key), OpenAlex 10 rps keyless, Emergent Mind 50/month free, alphaXiv feed quota-free, papers.cool unpublished-but-personal-site. And given this year's casualties (PWC dead; OpenReview/dblp/SciRate walled or blocked), keep per-source fail-soft behavior and re-verify this catalog quarterly.
