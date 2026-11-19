# Tech News & Tools source catalog

**Researched and verified live: 2026-11-19.** The goal was to make the
`Tech News` and `Tools & Releases` sections richer without turning the digest
into a general tech firehose. The chosen feeds are keyless RSS/Atom, owned by
the publication/lab, and capped tightly. `HN` remains a discovery source, but
it is no longer the only non-paper source.

## Selection criteria

- **Reputable owner** — first-party AI labs, established tech press, or a
  named independent AI writer.
- **Keyless and stable** — RSS/Atom over HTML scraping; no API keys, no paywall.
- **AI relevance** — AI-specific feeds are accepted directly; general feeds must
  pass a broad AI topic filter (`AI`, `LLM`, model/vendor names, GPU, agents...).
- **Bounded** — 2–4 items per feed, 7–30 day window; prereleases and build spam
  are filtered for GitHub releases.
- **Real summaries** — when a feed carries only a title, fetch the article's
  meta description or first substantive paragraph (bounded, best-effort).

## Chosen feeds (20)

| Group | Source key | Feed | Section | Cap / age |
| --- | --- | --- | --- | --- |
| Lab | `openai_news` | https://openai.com/news/rss.xml | tech_news | 3 / 14d |
| Lab | `deepmind_blog` | https://deepmind.google/blog/rss.xml | tech_news | 3 / 14d |
| Lab | `google_ai_blog` | https://blog.google/technology/ai/rss/ | tech_news | 3 / 14d |
| Lab | `google_research` | https://research.google/blog/rss/ | tech_news | 3 / 14d |
| Lab | `microsoft_research` | https://www.microsoft.com/en-us/research/feed/ | tech_news | 3 / 14d |
| Lab | `huggingface_blog` | https://huggingface.co/blog/feed.xml | tech_news | 3 / 14d |
| Press | `the_verge_ai` | https://www.theverge.com/rss/ai-artificial-intelligence/index.xml | tech_news | 4 / 7d |
| Press | `ieee_spectrum_ai` | https://spectrum.ieee.org/feeds/topic/artificial-intelligence.rss | tech_news | 4 / 14d |
| Press | `ars_technica` | https://feeds.arstechnica.com/arstechnica/technology-lab | tech_news | 3 / 7d + AI filter |
| Press | `mit_tech_review` | https://www.technologyreview.com/feed/ | tech_news | 3 / 7d + AI filter |
| Analysis | `simon_willison` | https://simonwillison.net/atom/everything/ | tech_news | 3 / 14d + AI filter |
| Analysis | `interconnects` | https://www.interconnects.ai/feed | tech_news | 3 / 14d |
| Analysis | `import_ai` | https://importai.substack.com/feed | tech_news | 2 / 14d |
| Tools | `gh_vllm` | https://github.com/vllm-project/vllm/releases.atom | tools_releases | 2 / 30d |
| Tools | `gh_ollama` | https://github.com/ollama/ollama/releases.atom | tools_releases | 2 / 30d |
| Tools | `gh_transformers` | https://github.com/huggingface/transformers/releases.atom | tools_releases | 2 / 30d |
| Tools | `gh_openwebui` | https://github.com/open-webui/open-webui/releases.atom | tools_releases | 2 / 30d |
| Tools | `gh_sglang` | https://github.com/sgl-project/sglang/releases.atom | tools_releases | 2 / 30d |
| Tools | `gh_unsloth` | https://github.com/unslothai/unsloth/releases.atom | tools_releases | 2 / 30d |
| Tools | `gh_comfyui` | https://github.com/comfyanonymous/ComfyUI/releases.atom | tools_releases | 2 / 30d |

Notes:

- **Google Research / Microsoft Research** require an AI topic hit because those
  blogs also publish health/science/podcast posts. The feed's `<category>` tags
  are used as a fallback summary when no article description exists.
- **Hugging Face** carries no `<description>`; its summary comes from the
  article's meta description or first substantive paragraph. Without that
  hydration the writer prompt would have to say "no description provided".
- **Unsloth** publishes feature-level releases tagged `-beta`; the prerelease
  filter intentionally targets `rc*`, `.dev`, `nightly`, `trunk/` and similar
  build labels, not every `beta` tag. It does not filter a stable-looking title
  whose URL is an rc build (Ollama does this), because the URL is checked too.

## Rejected / deferred

| Candidate | Why not now |
| --- | --- |
| Anthropic news | No RSS at `/news.rss`, `/rss.xml`, or `/feed.xml` (404 on 2026-11-19); scrape later if needed. |
| Meta AI blog | No RSS at `/blog/rss.xml` or `/feed/` (404); `about.fb.com/news/feed/` is general Meta news, not AI-specific. |
| VentureBeat AI | Feed returned HTTP 429 from this host during the survey; unreliable for a daily job. |
| TechCrunch AI | Feed works, but adds startup/business stories with lower technical signal; optional, not default. |
| NVIDIA blog | Works, but the main feed is general gaming/enterprise news; would need a strict AI filter. |
| PyTorch releases Atom | Returns `trunk/...` commits, not stable version releases. |
| llama.cpp releases Atom | Every build (`b12532`, ...) looks like a release; too noisy for a daily digest. |
| LangChain releases Atom | Package-level patch versions (`langchain-openai==1.8.3`); high frequency, low marginal value. |
| Aider releases Atom | Mostly `.dev` prereleases. |

## Pipeline behavior

- One registry source (`feeds`) owns all configured feeds. Each feed fails
  independently; `fetch_feeds` raises only if **every** feed fails, so one dead
  site never blocks the digest.
- `Item.section_hint` carries the feed's intended section. GitHub releases are
  tools even when the title does not match the heuristic release regex.
- The editor LLM may still reclassify a non-paper item between `tech_news` and
  `tools_releases`; paper sources cannot leave `papers`.
- `balanced_pool` reserves about 20% of the 80-item editor pool for Tech News
  and 12% for Tools (minimum 8 and 5), then fills the rest by score. Without
  this, papers (topic hits + citations + source weight) crowded out every news
  item before the LLM saw it.
- A small source-quality bonus lifts first-party/analysis feeds above unvetted
  front-page links; off-topic HN links are removed from the editorial pool.
- Reader-facing labels are per feed (`OpenAI`, `Google DeepMind`, `The Verge`,
  `vLLM`, ...), configured in `daily_digest/source_labels.py` and overridable
  with each feed's `label`.

## Verification (2026-11-19)

- `uv run daily-digest smoke` → **253 items, 0 source failures**; feed source
  contributed **48 items** across all 20 feeds.
- `uv run daily-digest run --force` → **exit 0**, model `deepseek-v4.1-flash`,
  **7 papers / 3 tech_news / 2 tools** (previous digest before this work:
  11 papers / 1 tech_news / 0 tools). Tech News: Hugging Face, Google DeepMind,
  Hugging Face; Tools: vLLM, Unsloth.
- Full suite: **298 passed** (after the feed and section tests).
- Repeated live probes tripped arXiv's 429 limit for alphaXiv's metadata call.
  alphaXiv now logs and skips on a metadata 429/timeout instead of marking the
  whole digest degraded; the feeds themselves delivered all 48 items.

## Sprint follow-up: HN hydration, diversity, feed health (2026-11-19)

- **HN link hydration** (`sources.hn.hydrate`, limit 12, best-effort, before
  `balanced_pool`): live run logged `hn hydration: 4/4 link posts hydrated` and
  the digest contains **zero** "No description provided" items.
- **Tech News source diversity** (`llm.diversify_tech_news`): the live run
  replaced the second Hugging Face pick with Import AI, so Tech News ran with
  **three distinct sources** — Hugging Face, Import AI, Google DeepMind —
  without padding (8 papers / 3 tech news / 1 tool).
- **`daily-digest health`**: live output `feeds: 20/20 healthy`, exit 0.
- Full suite: **325 passed**. `run --force` exit 0 with no new degraded causes;
  digest contract unchanged (12 uid / 12 like / 12 ask, `digest-data` blob
  intact, `open --web latest` exit 0).
