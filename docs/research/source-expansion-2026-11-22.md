# Mở rộng candidate pool cho daily-digest — research 2026-11-22

> **Phạm vi:** tìm nguồn mới để tăng số bài chất lượng cho pipeline
> `fetch → merge/dedup → loại bài đã hiện → balanced pool → editor LLM`.
> **Cách kiểm chứng:** đọc code/config hiện tại, đọc catalog cũ
> (`docs/paper-sources.md`, `docs/tech-news-sources.md`), rồi probe trực tiếp
> RSS/Atom/API bằng HTTP ngày **2026-11-22**. Các URL không truy cập được hoặc
> không có feed đều được ghi rõ là chưa xác minh/loại.
> **Status:** top 5 đã triển khai ngày 2026-11-22 (`epoch_ai`, `apple_ml`,
> `ai2_blog`, `vllm_blog`, `pytorch_blog`); 25/25 feed healthy.
> **Kết luận ngắn:** thêm 10 aggregator nữa **không** giải quyết được bài toán
> 30 bài/ngày, vì phần lớn sẽ trả về cùng arXiv id và bị dedup. Cần thêm nguồn
> **nội dung gốc** (lab/engineering/safety/benchmark), thêm **category arXiv**
> có chọn lọc, và dùng backfill cho ngày yên tĩnh.

---

## 0. TL;DR

- **Nút thắt không phải số lượng feed.** Ngày Chủ nhật 2026-11-22, log ghi
  `dropped 72 items already shown on previous days`, chỉ còn 16 bài mới; arXiv
  RSS cũng không có announcement mới trong ngày Chủ nhật. Thêm feed paper chỉ
  làm tăng cùng một tập arXiv id.
- **5 nguồn nên thêm ngay:** Epoch AI, Apple Machine Learning, vLLM blog,
  PyTorch blog, Ai2 blog. Đây là nội dung gốc, ít trùng, chất lượng cao.
- **4 nguồn tiếp theo:** Meta Engineering, Modal, Alignment Forum, METR —
  ML systems, engineering, safety/evals; volume thấp nhưng tín hiệu rất riêng.
- **Gap lớn nhất không có feed:** Anthropic Research/Engineering/Alignment
  Science. Nội dung rất đúng tệp độc giả nhưng chỉ có HTML; defer trừ khi chấp
  nhận một parser HTML có test.
- **Tăng volume có kiểm soát:** thêm arXiv `stat.ML`, `cs.RO`, `cs.SE` với cap
  thấp; thêm AWS ML, NVIDIA Developer, Databricks nhưng bắt buộc topic filter
  và cap 2/ngày.
- **Không nên thêm:** Anthropic/Meta/xAI/Apollo/LMArena/Cohere… vì không có
  RSS/Atom công khai ở các path đã kiểm tra; The Gradient/Chip Huyen đã ngừng
  cập nhật; VnExpress/Genk/NIST/LessWrong quá rộng hoặc lệch tệp độc giả.
- **Ngày yên tĩnh vẫn cần backfill.** Source expansion nâng trần chất lượng,
  không biến Chủ nhật thành ngày có 30 bài mới. Dùng `--backfill`/size-change
  backfill đã có, hoặc hạ target.

---

## 1. Hiện trạng pool

### 1.1 Nguồn đang chạy

Theo `daily_digest/config.py` và `daily_digest/sources/`:

| Nhóm | Nguồn | Cap/ngày | Vai trò |
| --- | --- | --- | --- |
| Paper | arXiv RSS `cs.CL`, `cs.LG`, `cs.AI` | 40/category | new announcements |
| Paper | Hugging Face Daily Papers | 30 | HF community upvotes |
| Paper | alphaXiv hot feed | 20 | researcher upvotes |
| Paper | Emergent Mind trending | 20 | cross-platform attention |
| Discovery | Hacker News front page | 60 | general tech, AI filter |
| Lab/blog | 20 RSS feeds (OpenAI, DeepMind, Google, Microsoft, HF, The Verge, IEEE, Ars, MIT TR, Simon Willison, Interconnects, Import AI) | 2–4/feed | news/analysis |
| Tools | 7 GitHub release Atom feeds (vLLM, Ollama, Transformers, Open WebUI, SGLang, Unsloth, ComfyUI) | 2/feed | stable releases |

`balanced_pool` cap 80; editor chọn 1–30. Vì vậy thêm feed **không** làm pool
nổ tung, nhưng cũng không tự động tạo thêm bài **mới**.

### 1.2 Bằng chứng ngày yên tĩnh

Log run 09:04 ngày 2026-11-22:

```text
dropped 72 items already shown on previous days
LLM ranking OK: 16 items
digest size: requested 30, selected 16 (candidate pool short)
```

Probe `https://export.arxiv.org/rss/cs.CL` và các category hiện tại trong ngày
Chủ nhật trả về feed hợp lệ nhưng **0 item** — arXiv không announce bài mới vào
Chủ nhật. Vì vậy 16 bài mới chủ yếu đến từ feed/alphaXiv/HN, không phải arXiv.

**Hệ quả:** muốn tăng số bài **chất lượng** trong ngày thường, thêm nguồn gốc;
muốn đủ 30 trong ngày Chủ nhật, phải backfill hoặc hạ target. Đừng thêm feed
rác chỉ để đủ số.

---

## 2. Tiêu chí và cách chấm

Mỗi nguồn được chấm 1–5 theo:

- **Quality:** bài gốc, có phương pháp/kết quả/số liệu, không phải PR.
- **Relevance:** LLM, agent, inference, training, evaluation, safety, systems,
  tooling, open-source AI.
- **Freshness/Volume:** nhịp cập nhật và số item unique/ngày.
- **Uniqueness:** không trùng arXiv id/nguồn hiện có.
- **Accessibility:** RSS/Atom/API chính thức, keyless hoặc free key.
- **Integration:** thêm vào `_default_feeds`/config trong 1–2 giờ.
- **Risk:** paywall, ToS, noise, bus factor.

Trọng số: Quality 30%, Relevance 20%, Uniqueness 15%, Volume 10%,
Accessibility 10%, Reliability 5%, Integration 5%, Risk 5%.

---

## 3. Bảng ứng viên

> **Verified** = HTTP 200 + parse được feed + có item mẫu ngày 2026-11-22.
> **No feed** = đã thử RSS/Atom path và/hoặc tìm `<link rel="alternate">`,
> không thấy feed công khai; không khuyến nghị scrape lúc này.

| # | Nguồn | Feed/API | Loại | Nhịp | Item unique/ngày | Quality | Trùng | Tích hợp | Rủi ro | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Epoch AI | `https://epoch.ai/atom.xml` | data/analysis | 1–2/tuần | 0.2 | 5 | Thấp | config | thấp | **Must** |
| 2 | Apple ML | `https://machinelearning.apple.com/rss.xml` | research | 2–3/tuần | 0.4 | 5 | Thấp | config | thấp | **Must** |
| 3 | vLLM blog | `https://vllm.ai/blog/rss.xml` | inference eng | 1–2/tuần | 0.2 | 5 | Thấp | config | thấp | **Must** |
| 4 | PyTorch blog | `https://pytorch.org/blog/feed.xml` | systems/training | 2–4/tuần | 0.4 | 4 | Thấp | config + topic | có bài community | **Must** |
| 5 | Ai2 blog | `https://allenai.org/rss.xml` | research/models | 1–2/tuần | 0.2 | 5 | Thấp | config | thấp | **Must** |
| 6 | Modal blog | `https://modal.com/blog/atom.xml` | infra/engineering | 1–2/tuần | 0.2 | 4 | Thấp | config | thấp | **Must** |
| 6b | Meta Engineering | `https://engineering.fb.com/feed/` | ML systems/infra | 2–3/tuần | 0.25 | 5 | Thấp | config | có bài non-AI | **Must** |
| 7 | Alignment Forum | `https://www.alignmentforum.org/feed.xml` | safety/alignment | 2–3/tuần | 0.4 | 4 | Thấp | config | opinion/noise | **Must** |
| 8 | METR | `https://metr.org/feed.xml` | evals/safety | 1–2/tháng | 0.05 | 5 | Thấp | config | volume thấp | **Should** |
| 9 | arXiv `stat.ML` | `https://export.arxiv.org/rss/stat.ML` | papers | ngày | cao | 3 | cao với `cs.LG` | config | lý thuyết/noise | **Should** |
| 10 | arXiv `cs.RO` | `https://export.arxiv.org/rss/cs.RO` | papers | ngày | cao | 3 | trung bình | config | robotics noise | **Should** |
| 11 | arXiv `cs.SE` | `https://export.arxiv.org/rss/cs.SE` | papers | ngày | trung bình | 3 | trung bình | config | software eng noise | **Should** |
| 11b | arXiv `cs.CR` + LLM filter | `https://export.arxiv.org/rss/cs.CR` | papers/security | ngày | trung bình sau filter | 3 | trung bình | config + filter | raw feed đa số crypto | **Should** |
| 12 | arXiv `cs.NE` | `https://export.arxiv.org/rss/cs.NE` | papers | ngày | trung bình | 2 | trung bình | config | niche | Nice |
| 13 | AWS ML blog | `https://aws.amazon.com/blogs/machine-learning/feed/` | engineering | 1–3/ngày | 1–2 sau filter | 3 | trung bình | config + topic | broad | **Should** |
| 14 | NVIDIA Developer | `https://developer.nvidia.com/blog/feed/` | engineering | 1–2/ngày | 1 sau filter | 3 | trung bình | config + topic | broad | **Should** |
| 15 | Databricks blog | `https://www.databricks.com/feed` | data/AI eng | 1–2/ngày | 1 sau filter | 3 | trung bình | config + topic | broad | **Should** |
| 16 | Latent Space | `https://www.latent.space/feed` | analysis/news | 1–2/ngày | 1 | 3 | trung bình | config + topic | AINews volume | **Should** |
| 17 | TensorRT-LLM releases | `https://github.com/NVIDIA/TensorRT-LLM/releases.atom` | release | 1–2/tuần | 0.2 | 4 | thấp | config | rc filter | **Should** |
| 18 | TRL releases | `https://github.com/huggingface/trl/releases.atom` | release | 1–2/tuần | 0.2 | 3 | thấp | config | version noise | **Should** |
| 19 | MCP servers releases | `https://github.com/modelcontextprotocol/servers/releases.atom` | tools | 1/tuần | 0.15 | 3 | thấp | config | thấp | **Should** |
| 20 | Understanding AI | `https://www.understandingai.org/feed` | analysis | 1–2/tuần | 0.2 | 4 | thấp | config | thấp | **Should** |
| 20b | Vals AI | `https://www.vals.ai/blogs/rss.xml` | third-party evals | 2–3/tuần | 0.4 | 3 | trung bình | config | pop/policy posts | **Should** |
| 21 | Sebastian Raschka | `https://sebastianraschka.com/rss_feed.xml` (magazine feed cũng chạy) | analysis | 1–2/tuần | 0.15 | 5 | thấp | config | volume thấp | **Should** |
| 22 | One Useful Thing | `https://www.oneusefulthing.org/feed` | analysis | 1–2/tháng | 0.05 | 4 | thấp | config | volume thấp | **Should** |
| 23 | BAIR blog | `https://bair.berkeley.edu/blog/feed.xml` | research | 1–2/tháng | 0.05 | 4 | thấp | config | volume thấp | Nice |
| 24 | Mistral news | `https://mistral.ai/news/rss` | lab/product | 1–2/tháng | 0.05 | 3 | thấp | config | product news | Nice |
| 25 | Zenn AI | `https://zenn.dev/topics/ai/feed` | Japanese eng | nhiều/ngày | cao | 2 | thấp | config + filter | noise | Nice (ja) |
| 26 | Qiita AI | `https://qiita.com/tags/ai/feed` | Japanese eng | nhiều/ngày | cao | 2 | thấp | config + filter | noise | Nice (ja) |
| 27 | Hamel Husain | `https://hamel.dev/index.xml` | evals | 1/tháng | 0.03 | 4 | thấp | config | volume thấp | Nice |
| 28 | GOV.UK AISI | `https://www.gov.uk/search/news-and-communications.atom?organisations%5B%5D=ai-security-institute` | policy/safety | 1/tháng | 0.03 | 3 | thấp | config | policy, ít kỹ thuật | Nice |
| 29 | Lilian Weng | `https://lilianweng.github.io/index.xml` | research | 1/quý | 0.01 | 5 | thấp | config | rất thấp | Nice |
| 29b | Transformer Circuits | `https://transformer-circuits.pub/feed.xml` | interpretability | 1/tháng | 0.02 | 5 | thấp | config | rất thấp | Nice |
| 30 | Together AI blog | `https://www.together.ai/blog/rss.xml` | product/release | 1–2/ngày | 1 | 2 | thấp | config | marketing | Nice |
| 31 | DeepSpeed releases | `https://github.com/microsoft/DeepSpeed/releases.atom` | release | 1–2/tuần | 0.2 | 3 | thấp | config + nightly filter | nightly noise | Nice |
| 32 | The Gradient | `https://thegradient.pub/rss/` | analysis | dừng | 0 | 3 | thấp | — | stale từ 02/2026 | Reject |
| 33 | Chip Huyen | `https://huyenchip.com/feed.xml` | analysis | dừng | 0 | 4 | thấp | — | stale từ 01/2025 | Reject |
| 34 | VnExpress Số hóa | `https://vnexpress.net/rss/so-hoa.rss` | general tech | nhiều/ngày | cao | 1 | thấp | config | quá rộng | Reject |
| 35 | Genk | `https://genk.vn/rss/home.rss` | general tech | nhiều/ngày | cao | 1 | thấp | config | quá rộng | Reject |

Các nguồn **không có feed công khai** tại path đã thử (không đưa vào bảng
Must): Anthropic News/Research, Meta AI blog, xAI News, Apollo Research,
Cohere blog, LMArena blog, Databricks blog path `/blog`, Anyscale blog,
LangChain blog, LlamaIndex blog, EleutherAI blog, Stanford HAI, NIST AI.
Không nên scrape các trang này chỉ để thêm số; chi phí bảo trì cao và dễ vỡ.

**Anthropic Research / Engineering / Alignment Science** là ngoại lệ đáng cân
nhắc nhất: bài agent memory, source control, harness design, safety eval rất
đúng tệp độc giả, nhưng không có RSS. Mẫu đã kiểm tra:
[Claude solves two open problems in the physics of black holes](https://www.anthropic.com/research/claude-black-hole-physics)
(2026-11-17),
[Building strong safety evaluations](https://www.anthropic.com/research/building-strong-safety-evaluations)
(2026-11-13),
[Worse Together: How Performance Breaks Down in Multi-User Multi-Agent Teams](https://alignment.anthropic.com/2026/worse-together/)
(2026-11-11). Nếu muốn thêm, làm một parser HTML riêng có test và fail-soft;
đây là **Should/Defer**, không phải Must của đợt này vì không có feed contract.

Các nguồn high-value khác không có feed: **Thinking Machines** (4 bài/7 tháng,
mẫu [End-to-End 4-Bit Training](https://thinkingmachines.ai/blog/end-to-end-4-bit-training/),
2026-11-13), **Apollo Research** (3 bài/60 ngày, mẫu
[Towards embedded evaluations for AI monitoring](https://www.apolloresearch.ai/blog/towards-embedded-evaluations-for-ai-monitoring),
2026-11-19), **Arena/LMArena** (blog HTML; leaderboard Cloudflare 403). Chỉ
thêm nếu chấp nhận parser HTML và chi phí bảo trì.

Các nguồn bị loại vì lý do khác: **Gradient Flow** trả 403 với Chrome UA/article
URL (Cloudflare) nên không ổn định cho `httpx`; **Answer.AI** bài mới nhất
2026-08-19; **SemiAnalysis** RSS cũ/paywall; **Sakana AI** feed có bài dated
2026-11-24 (tương lai, đáng ngờ) và link tương đối; **Qiita AI** volume cao
nhưng depth thấp, chỉ dùng như nguồn phụ cho `ja` nếu thật sự cần.

---

## 4. Must/Should — bằng chứng và mẫu

**Lưu ý section:** `FeedEntry` hiện chỉ cho `tech_news` và `tools_releases`.
Vì vậy Apple/Ai2/Epoch/Modal/Meta Engineering sẽ vào **Tech News**, không vào
**Research**. Nếu muốn chúng vào Research, phải mở rộng schema và validation
(một code change riêng), đừng giả định feed blog tự thành paper.

**Lưu ý filter:** không bật `require_topic=True` cho các feed first-party hẹp
(Apple, Ai2, Modal, PyTorch, vLLM). Probe cho thấy filter hiện tại bỏ sót bài
tốt: `Depth Pro 2`, `Fast by Default: Helion Kernels`, `Theorizer comes to
Asta` đều không match topic list. Chỉ dùng `require_topic=True` cho feed rộng
(AWS, NVIDIA, Databricks) và bổ sung các topic còn thiếu như `kernel`,
`serving`, `quantization`, `RLHF`, `reasoning`, `evaluation`, `diffusion`,
`3D`, `PyTorch`, `vLLM` nếu muốn lọc chặt hơn.

### 4.1 Epoch AI — `https://epoch.ai/atom.xml`

- **Vì sao:** phân tích định lượng về compute, inference capacity, chip supply,
  benchmark; nội dung gốc, không trùng arXiv.
- **Mẫu (2026-11-22):**
  - [Agentic inference capacity grew 4.6× in a year, versus 2.6× for compute capacity](https://epoch.ai/data-insights/agentic-inference-capacity-growth) — 2026-11-18.
  - [Anthropic’s compute spending is increasing by 4x per year, outpacing OpenAI’s 3x](https://epoch.ai/data-insights/anthropic-openai-compute-spend-growth) — 2026-11-18.
  - [What you need to know about AI chips](https://epoch.ai/publications/chips-topic-overview) — 2026-11-18.
- **Tích hợp:** một `FeedEntry`, `max_items=2`, `max_age_days=14`, section
  `tech_news`; không cần hydrate vì feed có description.
- **Rủi ro:** volume thấp; đừng kỳ vọng nó lấp đầy 30 bài.

### 4.2 Apple Machine Learning — `https://machinelearning.apple.com/rss.xml`

- **Vì sao:** research blog có phương pháp, kết quả, model/dataset cụ thể;
  thường bị bỏ sót vì Apple không ồn ào.
- **Mẫu:**
  - [Depth Pro 2: Sharp and Temporally Consistent Metric Monocular Depth](https://machinelearning.apple.com/research/depth-pro-2-monocular) — 2026-11-20.
  - [Split-and-Scale Latent 3D Representations](https://machinelearning.apple.com/research/split-scale-latent-3d) — 2026-11-16.
  - [Theoretical Limits of Language Model Alignment](https://machinelearning.apple.com/research/theoretical-limits-alignment) — 2026-11-12.
- **Tích hợp:** `max_items=3`, `max_age_days=21`, `tech_news`.
- **Rủi ro:** đôi khi lệch sang vision/3D; vẫn trong tệp AI researcher.

### 4.3 vLLM blog — `https://vllm.ai/blog/rss.xml`

- **Vì sao:** engineering write-up về serving/inference, model support, kernel,
  throughput; bổ sung cho GitHub release feed hiện có.
- **Mẫu:**
  - [Inkling 2 Mini on vLLM: Day-0 Support for a Looped Model](https://vllm.ai/blog/2026-11-20-inkling2-mini) — 2026-11-20.
  - [Keeping Agents Fast: High-Interactivity Decode with FlyDSL MonoKernels in vLLM](https://vllm.ai/blog/2026-11-18-flydsl-monokernels) — 2026-11-18.
  - [DeepSeek-V4.1-Flash on Vera Rubin NVL72: 58x Throughput vs. GB300 NVL72 at 387 tokens/s](https://vllm.ai/blog/2026-11-12-deepseek-v41-flash-vera-rubin) — 2026-11-12.
- **Tích hợp:** `max_items=2`, `tech_news`; không cần hydrate.
- **Rủi ro:** trùng chủ đề với GitHub release vLLM; dedup theo URL/arXiv id
  không bắt được vì URL khác. Cần dedup theo title/source hoặc chấp nhận 2 bài
  gần nhau.

### 4.4 PyTorch blog — `https://pytorch.org/blog/feed.xml`

- **Vì sao:** kernel, distributed training, TorchTitan, ExecuTorch, TPU/GPU
  systems; rất đúng tệp AI engineer.
- **Mẫu (bỏ qua bài community):**
  - [Fast by Default: Compile-Time Heuristics for Helion Kernels](https://pytorch.org/blog/fast-by-default-compile-time-heuristics-for-helion-kernels/) — 2026-11-12.
  - [Integrating SGLang into Spyre in Under a Week with AI](https://pytorch.org/blog/integrating-sglang-into-spyre-in-under-a-week-with-ai/) — 2026-11-12.
  - [Training a 1T-Parameter MoE on EU public infrastructure with PyTorch and TorchTitan](https://pytorch.org/blog/training-a-1t-parameter-moe-on-eu-public-infrastructure-with-pytorch-and-torchtitan/) — 2026-11-12.
- **Tích hợp:** `max_items=2`, `require_topic=True`, `max_age_days=14`;
  topic filter sẽ loại bài award/community.
- **Rủi ro:** feed có bài community/award; nếu không filter sẽ làm loãng.

### 4.5 Ai2 blog — `https://allenai.org/rss.xml`

- **Vì sao:** open models, benchmarks, tooling, research; nội dung gốc từ lab.
- **Mẫu:**
  - [Theorizer comes to Asta](https://allenai.org/blog/theorizer-in-asta) — 2026-11-19.
  - [Ai2 and Taylor Geospatial partner to make geospatial AI easier to compare, run, and build on](https://allenai.org/blog/taylor-geospatial-partnership) — 2026-11-18.
  - [XYBench: Helping with the problem behind the question](https://allenai.org/blog/xybench) — 2026-11-13.
- **Tích hợp:** `max_items=2`, `max_age_days=21`, `tech_news`.
- **Rủi ro:** volume thấp; một số bài policy/partnership, cần topic filter nhẹ.

### 4.6 Modal blog — `https://modal.com/blog/atom.xml`

- **Vì sao:** infra/engineering cho inference, sandbox, GPU workload; bài có
  kiến trúc và số liệu thực.
- **Mẫu:**
  - [How Abundant designed efficient rollout architecture with Modal Sandboxes](https://modal.com/blog/abundant-efficient-rollout-architecture-with-modal-sandboxes) — 2026-11-19.
  - [Building new research tools for Maya epigraphy on Modal](https://modal.com/blog/scaling-intelligence-asya) — 2026-11-18.
  - [Scaling Intelligence: A landmark commission and exhibition](https://modal.com/blog/scaling-intelligence) — 2026-11-13.
- **Tích hợp:** `max_items=2`, `tech_news`.
- **Rủi ro:** có bài không thuần AI; topic filter hoặc để editor loại.

### 4.6b Meta Engineering — `https://engineering.fb.com/feed/`

- **Vì sao:** ML systems, ranking infrastructure, agent tooling ở quy mô lớn;
  bài có kiến trúc, số liệu, trade-off vận hành.
- **Mẫu:**
  - [How Meta Uses AI Agents to Scale ML Innovations Across Ads Ranking Models](https://engineering.fb.com/2026/11/18/ml-applications/ai-agents-to-scale-ml-innovations-across-ads-ranking-models/) — 2026-11-18.
  - [Design Once, Deploy at Scale: Building a Template-Driven ML Ecosystem](https://engineering.fb.com/2026/11/18/ml-applications/design-once-deploy-at-scale-template-driven-ml-ecosystem/) — 2026-11-18.
  - [Cuttlefish on Mac: Running Android’s Virtual Device Framework Natively on Apple Silicon](https://engineering.fb.com/2026/11/13/android/cuttlefish-on-mac/) — 2026-11-13.
- **Tích hợp:** `max_items=2`, `max_age_days=21`, không bật `require_topic`
  (bài AI nằm lẫn infra; editor lọc).
- **Rủi ro:** feed có bài Android/infra không liên quan; cap thấp.

### 4.7 Alignment Forum — `https://www.alignmentforum.org/feed.xml`

- **Vì sao:** safety/alignment research và discussion; tín hiệu khác hoàn toàn
  với paper feed.
- **Mẫu:**
  - [Solomonoff induction with reflective oracles](https://www.alignmentforum.org/posts/nvrFYAwciyyj9T5ir/solomonoff-induction-with-reflective-oracles) — 2026-11-19.
  - [Looping a transformer increases no-CoT capabilities more than general capabilities](https://www.alignmentforum.org/posts/uxsDuWWHNTpKrsF6P/looping-a-transformer-increases-no-cot-capabilities-more) — 2026-11-12.
  - [How I'm thinking about different types of automated alignment](https://www.alignmentforum.org/posts/NFkj9J2BBLSjNuH5G/how-i-m-thinking-about-different-types-of-automated) — 2026-11-11.
- **Tích hợp:** `max_items=2`, `max_age_days=14`, `tech_news`.
- **Rủi ro:** opinion/alignment-heavy; có thể quá niche với độc giả đại chúng.

### 4.8 METR — `https://metr.org/feed.xml` (Should, low volume)

- **Vì sao:** capability evaluation, alignment eval, R&D automation; dữ liệu
  đánh giá có phương pháp, rất khó thay thế.
- **Mẫu:**
  - [AI R&D-relevant model capabilities are improving rapidly and are getting harder to measure](https://metr.org/blog/2026-11-20-q4-2026-capability-update/) — 2026-11-20.
  - [Measuring alignment eval tells](https://metr.org/notes/2026-11-16-measuring-alignment-eval-tells/) — 2026-11-16.
  - [Review of the “Risks from automated R&D” section in Anthropic’s Risk Report](https://metr.org/blog/2026-11-05-rd-section-anthropic-risk-report-august-2026-review/) — 2026-11-05.
- **Tích hợp:** `max_items=1`, `max_age_days=30`; volume thấp nên đừng cap chặt
  quá mức.
- **Rủi ro:** 1–2 bài/tháng; chỉ nên là một phần của pool, không phải nguồn
  volume.

---

## 5. Should/Nice — cách dùng đúng

### 5.1 Volume có kiểm soát

- **arXiv `stat.ML`, `cs.RO`, `cs.SE`, `cs.CR`:** thêm vào
  `ArxivCfg.categories` với `max_per_category=15–20`, không dùng 40 như category
  hiện tại. Đây là cách tăng volume rẻ nhất nhưng dễ nhiễu; phải đo overlap với
  `cs.LG`/`cs.AI`.
  - `stat.ML` thiên lý thuyết; `cs.RO` robotics/embodied; `cs.SE` coding agent,
    vulnerability, software engineering; `cs.CR` cần filter `LLM` hoặc
    `language model` vì raw feed đa số crypto/security.
  - Probe API ngày 2026-11-22 xác nhận các category có bài mới trong tuần
    (Chủ nhật RSS trống, nhưng API trả paper ngày 2026-11-19).
- **AWS ML / NVIDIA Developer / Databricks:** chỉ thêm với `require_topic=True`,
  `max_items=2`, `max_age_days=7`. Feed rộng, nếu không filter sẽ có bài
  marketing/data platform không liên quan.
- **Latent Space:** cap 1–2; AINews hàng ngày có thể chiếm chỗ. Chỉ giữ nếu
  editor thực sự chọn; nếu không, bỏ.
- **Zenn/Qiita:** chỉ dùng cho locale `ja` hoặc như nguồn phụ; volume rất cao,
  quality biến động. `max_items=1–2`, topic filter chặt.

### 5.2 Release/tool feeds

- **TensorRT-LLM:** stable `v1.3.0` ngày 2026-11-20; feed có rc, adapter hiện
  tại đã lọc `rc`, phù hợp.
- **TRL:** stable `v1.18.2` ngày 2026-11-19; tín hiệu RLHF/RL fine-tuning.
- **MCP servers:** `v2.5.0` ngày 2026-11-18; tín hiệu tool ecosystem.
- **DeepSpeed:** có `v0.20.0` nhưng feed lẫn nightly; chỉ thêm nếu filter
  `nightly|trunk` hoạt động tốt.
- **PyTorch releases / llama.cpp / LangChain releases:** không thêm; quá nhiễu
  hoặc trùng package patch.

### 5.3 Analysis/safety

- **Understanding AI, One Useful Thing, BAIR, Mistral, Hamel, GOV.UK AISI,
  Lilian Weng:** chất lượng cao nhưng volume thấp. Thêm sau khi 5 Must đã ổn
  định; không dùng để giải bài toán 30 bài/ngày.
- **Sebastian Raschka:** feed chính `https://sebastianraschka.com/rss_feed.xml`
  có 6 bài/30 ngày; mẫu
  [The US-China Open-Weight Feedback Loop](https://sebastianraschka.com/blog/2026/us-china-open-weight-feedback-loop.html)
  (2026-11-21),
  [Pre-Training Without Learning Rate Decay](https://sebastianraschka.com/blog/2026/llm-pretraining-without-learning-rate-decay.html)
  (2026-11-17). Cần browser-like User-Agent; `httpx` mặc định có thể bị 406.
- **Vals AI:** feed `https://www.vals.ai/blogs/rss.xml` (13 bài/30 ngày); mẫu
  [Vals Misalignment Incidents: Towards understanding misaligned agent behavior](https://www.vals.ai/blogs/misalignment-incidents)
  (2026-11-20),
  [Building RollerCoasterTycoonBench: Can Decision Models Manage a Theme Park?](https://www.vals.ai/blogs/building-rctbench)
  (2026-11-19). Third-party evals, nhưng có bài pop/policy; cap 1–2.
- **Transformer Circuits:** feed `https://transformer-circuits.pub/feed.xml`;
  mẫu
  [Circuits Updates — October 2026](https://transformer-circuits.pub/2026/october-update/index.html)
  (2026-10-29). Rất hay nhưng 1 bài/tháng; chỉ Nice-to-have.
- **The Gradient, Chip Huyen:** đã ngừng cập nhật (02/2026 và 01/2025); không
  thêm.

---

### 5.4 Không nên thêm (đã kiểm tra)

- **OpenAlex / Semantic Scholar:** là enrichment/query API, không phải feed
  bài mới. OpenAlex trả 10k+ record/ngày nếu không filter; S2 keyless bị 429.
  Giữ vai trò citation enrichment, đừng dùng làm nguồn chính.
- **Artificial Analysis:** API key/model records, không có editorial feed;
  hữu ích cho benchmark lookup, không phải nguồn bài mới.
- **OpenReview:** `api.openreview.net` và `api2.openreview.net` trả 403
  `ChallengeRequiredError`; không đáng xử lý challenge cho một nguồn theo mùa.
- **HELM / SWE-bench / LiveBench / BFCL:** không có feed/dated updates; SWE-bench
  và LiveBench là leaderboard tĩnh/SPA; BFCL cập nhật lần cuối 2026-04-12.
- **NVIDIA Research:** RSS 200 nhưng trộn bài 2021 vào đầu feed; không dùng.
- **Meta AI / Qwen / ByteDance Seed:** không có feed ổn định, JS-heavy.
- **EleutherAI / BAIR / Terminal-Bench / Answer.AI:** quá thưa cho daily.
- **LessWrong curated:** quá rộng; Alignment Forum đã cover phần safety.
- **Inspect releases:** active nhưng là tooling release, không phải research;
  chỉ thêm nếu muốn phục vụ eval engineers.

---

## 6. Nguồn hiện có: giữ/giảm/thay thế

| Nguồn hiện có | Đánh giá | Hành động |
| --- | --- | --- |
| OpenAI/DeepMind/Google/Microsoft/HF blogs | first-party, tốt | Giữ; cap 3 |
| The Verge AI / Ars / MIT TR | breadth, tín hiệu kỹ thuật thấp hơn | Giữ cap 2–3; không thêm press tương tự |
| IEEE Spectrum AI | industry/research | Giữ cap 3 |
| Simon Willison | thực dụng, signal cao | Giữ cap 3 + AI filter |
| Interconnects / Import AI | phân tích sâu, tuần | Giữ; cap không quan trọng |
| arXiv/HF/alphaXiv/Emergent | cùng arXiv id, tín hiệu attention | Giữ; không kỳ vọng tăng unique volume |
| HN | discovery rộng | Giữ cap 60 + AI filter |
| 7 GitHub release feeds | tool signal | Giữ; thêm tối đa 2–3 release feed stable |

**Không nên** giảm các lab blog để lấy chỗ cho general press; bài lab/blog có
unique content, còn press thường đưa lại cùng sự kiện.

Các đề xuất giảm trùng (bỏ `cs.AI`, giảm alphaXiv/Emergent, gộp ba feed Google,
bỏ bớt general press) chỉ nên làm **sau khi đo overlap 1–2 tuần**. Bỏ nguồn có
thể làm giảm coverage đúng lúc pool đang thiếu; ưu tiên thêm nguồn gốc trước.

---

## 7. Kế hoạch thử nghiệm 2 tuần

### Tuần 1 — “quality first”

Thêm 5 nguồn:

1. Epoch AI
2. Apple ML
3. vLLM blog
4. PyTorch blog (topic filter)
5. Ai2 blog

Đo mỗi ngày:

- raw items và unique items sau dedup;
- số item được editor chọn / tổng item của nguồn;
- duplicate rate với nguồn hiện có;
- source failure rate;
- section distribution;
- 3 mẫu ngẫu nhiên để review chất lượng.

**Keep** nếu: ≥2 unique item/tuần, ≥25% item được editor chọn hoặc được review
là “high signal”, 0 failure, duplicate <10%. **Drop** nếu <1 item/2 tuần hoặc
toàn bài marketing/off-topic.

### Tuần 2 — “volume with guardrails”

Thêm:

- arXiv `stat.ML`, `cs.RO`, `cs.SE`, `cs.CR` (filter LLM) với cap 15–20/category;
- AWS ML + NVIDIA Developer + Databricks với `require_topic`, cap 2;
- TensorRT-LLM, TRL, MCP releases;
- Meta Engineering + Modal + Alignment Forum + METR (nếu tuần 1 ổn).

Đo thêm:

- unique arXiv id mới từ category mới;
- overlap với `cs.LG/cs.AI/cs.CL`;
- % bài bị editor loại vì off-topic;
- % pool bị một nguồn chiếm.

**Keep** nếu: category mới đóng góp ≥10 unique item/ngày và <30% overlap;
feed volume đóng góp ≥5 unique item/ngày, <30% off-topic, không chiếm >10% số
bài được chọn.

### Ngày yên tĩnh

- Không thêm nguồn rác để đủ 30.
- Dùng `--backfill` hoặc size-change backfill đã có.
- Nếu vẫn thiếu, hạ target hoặc hiển thị count thật (UI đã làm).

---

## 8. Assumptions / chưa xác minh

- Probe ngày **Chủ nhật 2026-11-22**; arXiv RSS trống vào Chủ nhật. Volume
  ngày thường cần đo lại trong tuần 1.
- Một số site không có feed công khai tại path đã thử; có thể có feed sau
  Cloudflare/JS hoặc feed riêng chưa công bố. Không scrape khi chưa kiểm tra
  ToS.
- `Epoch`, `Apple`, `Ai2`, `Modal`, `vLLM`, `PyTorch`, `Alignment Forum`,
  `METR` đều trả HTTP 200 và parse được RSS/Atom ngày 2026-11-22.
- Các sample title/date lấy trực tiếp từ feed; link bài viết là link trong feed.
- Chưa đo chất lượng bằng blind human review; đây là research nguồn, không phải
  đánh giá nội dung từng bài.

---

## 9. References

- `docs/paper-sources.md` — catalog paper sources, verified 2026-11-19; đã kết
  luận Papers With Code dead, OpenReview blocked, Semantic Scholar/OpenAlex là
  enrichment, Emergent/alphaXiv đã được thêm.
- `docs/tech-news-sources.md` — catalog 20 feed hiện tại, rejected/deferred
  (Anthropic/Meta no RSS, VentureBeat 429, PyTorch releases trunk, llama.cpp
  builds, LangChain package versions).
- `daily_digest/config.py` — `_default_feeds`, `ArxivCfg`, `FeedsCfg`.
- `daily_digest/sources/` — adapter hiện tại.
- HTTP probes 2026-11-22:
  - Epoch `https://epoch.ai/atom.xml`
  - Apple `https://machinelearning.apple.com/rss.xml`
  - vLLM `https://vllm.ai/blog/rss.xml`
  - PyTorch `https://pytorch.org/blog/feed.xml`
  - Ai2 `https://allenai.org/rss.xml`
  - Modal `https://modal.com/blog/atom.xml`
  - Alignment Forum `https://www.alignmentforum.org/feed.xml`
  - METR `https://metr.org/feed.xml`
  - Meta Engineering `https://engineering.fb.com/feed/`
  - Vals AI `https://www.vals.ai/blogs/rss.xml`
  - Transformer Circuits `https://transformer-circuits.pub/feed.xml`
  - arXiv API: `https://export.arxiv.org/api/query?...cat:stat.ML...`
  - Anthropic Research/Alignment (HTML, no feed):
    `https://www.anthropic.com/research`, `https://alignment.anthropic.com/`
- Log local `logs/daily-digest.log` ngày 2026-11-22: 72 previous-day seen,
  16 selected / 30 requested.
