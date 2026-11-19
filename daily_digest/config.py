"""Configuration: dataclasses with safe defaults + optional config.yaml overlay."""

from __future__ import annotations

import dataclasses
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from daily_digest.model import Section
from daily_digest.util import LOG, PROJECT_ROOT, load_env_file


class ConfigError(Exception):
    """Fatal configuration problem (exit 2)."""


@dataclass
class InterestsCfg:
    topics: list[str] = field(
        default_factory=lambda: [
            "LLM",
            "language model",
            "NLP",
            "reinforcement learning",
            "RLHF",
            "GRPO",
            "AI agent",
            "agentic",
            "interpretability",
            "mechanistic",
            "transformer",
            "fine-tuning",
            "LoRA",
            "RAG",
            "distillation",
            "quantization",
            "inference",
            "vLLM",
            "benchmark",
            "reasoning",
            "open source",
            "developer tool",
            "AI engineering",
            "full stack",
        ]
    )
    weights: dict[str, float] = field(
        default_factory=lambda: {"papers": 1.0, "tech_news": 0.8, "tools_releases": 0.6}
    )
    # F5 keyword rules: mute = hard drop (title+summary, case-insensitive);
    # always = strong boost + ★ALWAYS marker for the editor. Mute beats always.
    mute: list[str] = field(default_factory=list)
    always: list[str] = field(default_factory=list)


@dataclass
class HnCfg:
    enabled: bool = True
    min_points: int = 30
    hits: int = 60


@dataclass
class HfPapersCfg:
    enabled: bool = True
    max_items: int = 30


@dataclass
class ArxivCfg:
    enabled: bool = True
    categories: list[str] = field(default_factory=lambda: ["cs.CL", "cs.LG", "cs.AI"])
    max_per_category: int = 40
    pause_seconds: float = 3.0  # arXiv asks for ~1 request / 3 seconds


@dataclass
class EmergentMindCfg:
    # emergentmind.com: trending arXiv papers ranked by cross-platform attention
    # (X, HN, Reddit, YouTube) — keyless RSS. The feed covers ALL arXiv subjects,
    # so a topic filter keeps the physics/math noise out of the pool.
    enabled: bool = True
    max_items: int = 20
    require_topic: bool = True
    topics: list[str] = field(
        default_factory=lambda: [
            "LLM",
            "LLMs",
            "language model",
            "machine learning",
            "deep learning",
            "neural network",
            "neural",
            "reinforcement learning",
            "transformer",
            "GPT",
            "artificial intelligence",
            "alignment",
            "interpretability",
            "agent",
            "reasoning",
            "fine-tuning",
            "attention",
            "diffusion model",
            "multimodal",
            "vision-language",
            "embedding",
            "tokeniz",
            "prompt",
            "RLHF",
            "reward model",
            "world model",
            "foundation model",
            "chatbot",
        ]
    )


@dataclass
class AlphaxivCfg:
    # alphaxiv.org "hot feed" (30-day window, app order): community-attention
    # ranking of arXiv papers, via the official MCP server. The feed returns bare
    # arXiv ids; titles/abstracts are resolved with one batched arXiv API call.
    # Needs a FREE key in .env (ALPHAXIV_API_KEY); without it the source skips itself.
    enabled: bool = True
    api_key_env: str = "ALPHAXIV_API_KEY"
    max_items: int = 20  # maps to the tool's `limit` (1-200)


@dataclass(frozen=True)
class FeedEntry:
    """One curated RSS/Atom feed.

    `section` is a hint for the heuristic fallback and the LLM's allowed
    section fallback; the editor may still reclassify non-paper items.
    """

    name: str
    url: str
    label: str = ""
    section: Section = "tech_news"
    max_items: int = 3
    max_age_days: int = 14
    require_topic: bool = False
    hydrate: bool = False  # fetch the article's meta description when summary is thin

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("feed name is required")
        if not self.url.lower().startswith(("http://", "https://")):
            raise ValueError(f"feed {self.name!r}: url must be http(s)")
        if self.section not in ("tech_news", "tools_releases"):
            raise ValueError(
                f"feed {self.name!r}: section must be tech_news or tools_releases"
            )
        if self.max_items < 1:
            raise ValueError(f"feed {self.name!r}: max_items must be >= 1")
        if self.max_age_days < 0:
            raise ValueError(f"feed {self.name!r}: max_age_days must be >= 0")


def _default_feeds() -> list[FeedEntry]:
    """Curated, keyless feeds verified live in docs/tech-news-sources.md.

    Labs first, then reputable press/analysis, then GitHub releases. Caps are
    deliberately small: the digest needs signal, not a second firehose.
    """
    return [
        # --- first-party AI labs -------------------------------------------
        FeedEntry(
            "openai_news",
            "https://openai.com/news/rss.xml",
            "OpenAI",
            max_items=3,
            hydrate=True,
        ),
        FeedEntry(
            "deepmind_blog",
            "https://deepmind.google/blog/rss.xml",
            "Google DeepMind",
            max_items=3,
            hydrate=True,
        ),
        FeedEntry(
            "google_ai_blog",
            "https://blog.google/technology/ai/rss/",
            "Google AI",
            max_items=3,
            hydrate=True,
        ),
        FeedEntry(
            "google_research",
            "https://research.google/blog/rss/",
            "Google Research",
            max_items=3,
            require_topic=True,
            hydrate=True,
        ),
        FeedEntry(
            "microsoft_research",
            "https://www.microsoft.com/en-us/research/feed/",
            "Microsoft Research",
            max_items=3,
            require_topic=True,
            hydrate=True,
        ),
        FeedEntry(
            "huggingface_blog",
            "https://huggingface.co/blog/feed.xml",
            "Hugging Face",
            max_items=3,
            hydrate=True,
        ),
        # --- reputable tech press (AI-specific unless require_topic) --------
        FeedEntry(
            "the_verge_ai",
            "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
            "The Verge",
            max_items=4,
            max_age_days=7,
        ),
        FeedEntry(
            "ieee_spectrum_ai",
            "https://spectrum.ieee.org/feeds/topic/artificial-intelligence.rss",
            "IEEE Spectrum",
            max_items=4,
        ),
        FeedEntry(
            "ars_technica",
            "https://feeds.arstechnica.com/arstechnica/technology-lab",
            "Ars Technica",
            max_items=3,
            max_age_days=7,
            require_topic=True,
        ),
        FeedEntry(
            "mit_tech_review",
            "https://www.technologyreview.com/feed/",
            "MIT Technology Review",
            max_items=3,
            max_age_days=7,
            require_topic=True,
        ),
        # --- independent AI analysis ---------------------------------------
        FeedEntry(
            "simon_willison",
            "https://simonwillison.net/atom/everything/",
            "Simon Willison",
            max_items=3,
            require_topic=True,
        ),
        FeedEntry(
            "interconnects",
            "https://www.interconnects.ai/feed",
            "Interconnects",
            max_items=3,
        ),
        FeedEntry(
            "import_ai",
            "https://importai.substack.com/feed",
            "Import AI",
            max_items=2,
        ),
        # --- tool releases (stable versions only; prereleases filtered) -----
        FeedEntry(
            "gh_vllm",
            "https://github.com/vllm-project/vllm/releases.atom",
            "vLLM",
            section="tools_releases",
            max_items=2,
            max_age_days=30,
        ),
        FeedEntry(
            "gh_ollama",
            "https://github.com/ollama/ollama/releases.atom",
            "Ollama",
            section="tools_releases",
            max_items=2,
            max_age_days=30,
        ),
        FeedEntry(
            "gh_transformers",
            "https://github.com/huggingface/transformers/releases.atom",
            "Transformers",
            section="tools_releases",
            max_items=2,
            max_age_days=30,
        ),
        FeedEntry(
            "gh_openwebui",
            "https://github.com/open-webui/open-webui/releases.atom",
            "Open WebUI",
            section="tools_releases",
            max_items=2,
            max_age_days=30,
        ),
        FeedEntry(
            "gh_sglang",
            "https://github.com/sgl-project/sglang/releases.atom",
            "SGLang",
            section="tools_releases",
            max_items=2,
            max_age_days=30,
        ),
        FeedEntry(
            "gh_unsloth",
            "https://github.com/unslothai/unsloth/releases.atom",
            "Unsloth",
            section="tools_releases",
            max_items=2,
            max_age_days=30,
        ),
        FeedEntry(
            "gh_comfyui",
            "https://github.com/comfyanonymous/ComfyUI/releases.atom",
            "ComfyUI",
            section="tools_releases",
            max_items=2,
            max_age_days=30,
        ),
    ]


@dataclass
class FeedsCfg:
    # One configurable source covering curated RSS/Atom feeds. Each feed fails
    # independently; bounded caps keep the candidate pool balanced.
    enabled: bool = True
    topics: list[str] = field(
        default_factory=lambda: [
            "AI",
            "artificial intelligence",
            "machine learning",
            "machine intelligence",
            "deep learning",
            "LLM",
            "NLP",
            "natural language",
            "language model",
            "GPT",
            "ChatGPT",
            "Claude",
            "Gemini",
            "OpenAI",
            "Anthropic",
            "DeepMind",
            "NVIDIA",
            "GPU",
            "agent",
            "agentic",
            "model",
            "neural",
            "transformer",
            "inference",
            "training",
            "benchmark",
            "alignment",
            "safety",
            "robotics",
            "multimodal",
            "computer vision",
            "generative",
            "open source",
        ]
    )
    entries: list[FeedEntry] = field(default_factory=_default_feeds)


@dataclass
class SourcesCfg:
    hn: HnCfg = field(default_factory=HnCfg)
    hf_papers: HfPapersCfg = field(default_factory=HfPapersCfg)
    arxiv: ArxivCfg = field(default_factory=ArxivCfg)
    emergent_mind: EmergentMindCfg = field(default_factory=EmergentMindCfg)
    alphaxiv: AlphaxivCfg = field(default_factory=AlphaxivCfg)
    feeds: FeedsCfg = field(default_factory=FeedsCfg)


@dataclass
class EnrichmentCfg:
    # OpenAlex (api.openalex.org, keyless): batch citation-count lookup for the
    # candidate pool — one request per day. Optional mailto joins the polite pool.
    enabled: bool = True
    email: str = ""


@dataclass
class FeedbackCfg:
    # F1: 👍/👎/🔖 from the popup, persisted append-only, consumed by the run.
    path: str = "feedback.jsonl"
    window_days: int = 14  # ratings older than this stop nudging prompts/scores
    max_prompt_titles: int = 10
    saved_cap: int = 5  # pinned "Nhìn lại" cards shown (+ "+N older" note)


@dataclass
class LlmCfg:
    # >>> TWO LLMs, two roles (one line each) <<<
    # `model`           = the EDITOR: picks which items make the digest.
    # `summarize_model` = the WRITER: writes each item's summary ("" = same model).
    # Any Console model id works: https://opencode.ai/inference/v1/models
    # e.g. deepseek-v4.1-flash (editor + writer) · glm-5.3 · kimi-k3 · claude-sonnet-5-5
    # Env overrides: DIGEST_LLM_MODEL / DIGEST_LLM_SUMMARIZE_MODEL
    model: str = "deepseek-v4.1-flash"
    summarize_model: str = ""  # empty -> reuse `model`
    summarize: bool = True  # writer LLM on/off
    summary_max_words: int = 70
    overview_language: str = "vi"  # language of the day-overview card ("vi", "en", ...)
    # F4: free-text context about the reader's current work, injected into prompts.
    # Empty profile_file disables it. Missing/unreadable file -> warning + "".
    profile_file: str = "profile.md"
    profile_max_chars: int = 600
    base_url: str = "https://opencode.ai/inference/go"  # OpenCode Go; pay-as-you-go: https://opencode.ai/inference
    chat_path: str = "/openai/v1/chat/completions"
    api_key_env: str = "OPENCODE_API_KEY"
    timeout_seconds: float = 90.0
    max_retries: int = 2
    temperature: float = 0.0
    top_n: int = 12
    max_pool: int = 80


@dataclass
class DigestCfg:
    output_dir: str = "output"
    template: str = "templates/digest.html.j2"


@dataclass
class NotifyCfg:
    enabled: bool = True
    # How the toast behaves on click:
    #   popup -> desktop popup window with the digest (default)
    #   file  -> open the digest HTML in the default browser
    #   none  -> plain toast, no click action
    launch: str = "popup"
    # Also open the desktop popup window automatically right after the toast
    # (this is the 09:00 "pop up on my desktop" behavior).
    popup: bool = True


@dataclass
class ScheduleCfg:
    time: str = "09:00"


@dataclass
class LogCfg:
    dir: str = "logs"
    level: str = "INFO"
    max_bytes: int = 1_048_576
    backups: int = 5


@dataclass
class StateCfg:
    path: str = "state.json"
    seen_days: int = 7


@dataclass
class MediaCfg:
    """Best-effort article-image enrichment (real figures/OG only)."""

    enabled: bool = True
    max_images: int = 6
    timeout_seconds: float = 8.0
    max_bytes: int = 5_000_000
    width: int = 1180
    quality: int = 85
    cache_dir: str = "output/media"
    llm_review: bool = True
    include_in_print: bool = False
    max_total_bytes: int = 1_500_000


@dataclass
class Config:
    interests: InterestsCfg = field(default_factory=InterestsCfg)
    sources: SourcesCfg = field(default_factory=SourcesCfg)
    llm: LlmCfg = field(default_factory=LlmCfg)
    media: MediaCfg = field(default_factory=MediaCfg)
    digest: DigestCfg = field(default_factory=DigestCfg)
    notify: NotifyCfg = field(default_factory=NotifyCfg)
    enrichment: EnrichmentCfg = field(default_factory=EnrichmentCfg)
    feedback: FeedbackCfg = field(default_factory=FeedbackCfg)
    schedule: ScheduleCfg = field(default_factory=ScheduleCfg)
    log: LogCfg = field(default_factory=LogCfg)
    state: StateCfg = field(default_factory=StateCfg)
    # Resolved (absolute) paths, set by load_config:
    output_dir: Path = field(
        default_factory=lambda: PROJECT_ROOT / "output", init=False
    )
    template_path: Path = field(
        default_factory=lambda: PROJECT_ROOT / "templates" / "digest.html.j2",
        init=False,
    )
    log_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "logs", init=False)
    state_path: Path = field(
        default_factory=lambda: PROJECT_ROOT / "state.json", init=False
    )
    feedback_path: Path = field(
        default_factory=lambda: PROJECT_ROOT / "feedback.jsonl", init=False
    )


def _merge_obj(obj: object, data: dict) -> None:
    names = {f.name for f in dataclasses.fields(obj)}  # type: ignore[arg-type]
    for key, value in data.items():
        if key not in names:
            LOG.warning("unknown config key '%s' ignored", key)
            continue
        current = getattr(obj, key)
        if dataclasses.is_dataclass(current) and isinstance(value, dict):
            _merge_obj(current, value)
        else:
            setattr(obj, key, value)


def _normalize_feed_entries(config: Config) -> None:
    """Turn YAML feed mappings into validated FeedEntry objects."""
    feeds = config.sources.feeds
    if not isinstance(feeds, FeedsCfg):
        raise ConfigError("sources.feeds must be a mapping")
    raw = feeds.entries
    if not isinstance(raw, list):
        raise ConfigError("sources.feeds.entries must be a list")
    entries: list[FeedEntry] = []
    seen: set[str] = set()
    for entry in raw:
        if isinstance(entry, FeedEntry):
            parsed = entry
        elif isinstance(entry, dict):
            try:
                parsed = FeedEntry(**entry)
            except (TypeError, ValueError) as exc:
                raise ConfigError(f"invalid sources.feeds entry: {exc}") from exc
        else:
            raise ConfigError(
                f"sources.feeds.entries must contain mappings, got {type(entry).__name__}"
            )
        if parsed.name in seen:
            raise ConfigError(f"duplicate feed name: {parsed.name!r}")
        seen.add(parsed.name)
        entries.append(parsed)
    config.sources.feeds.entries = entries


def load_config(path: Path | None = None) -> Config:
    """Defaults <- config.yaml overlay <- environment overrides. Never requires a config file."""
    load_env_file(PROJECT_ROOT / ".env")

    config = Config()
    config_path = Path(path) if path else PROJECT_ROOT / "config.yaml"
    if config_path.exists():
        import yaml

        try:
            data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise ConfigError(f"invalid YAML in {config_path}: {exc}") from exc
        if not isinstance(data, dict):
            raise ConfigError(f"top level of {config_path} must be a mapping")
        _merge_obj(config, data)

    _normalize_feed_entries(config)

    # Environment overrides (handy for quick model switches / CI)
    if os.environ.get("DIGEST_LLM_MODEL"):
        config.llm.model = os.environ["DIGEST_LLM_MODEL"]
    if os.environ.get("DIGEST_LLM_SUMMARIZE_MODEL"):
        config.llm.summarize_model = os.environ["DIGEST_LLM_SUMMARIZE_MODEL"]
    if os.environ.get("DIGEST_LLM_BASE_URL"):
        config.llm.base_url = os.environ["DIGEST_LLM_BASE_URL"]

    # F5 rule hygiene: wrong type -> warn + ignore; strip blanks.
    for rule_field in ("mute", "always"):
        value = getattr(config.interests, rule_field)
        if not isinstance(value, list):
            if value:
                LOG.warning(
                    "interests.%s must be a list; got %r — ignoring", rule_field, value
                )
            setattr(config.interests, rule_field, [])
        else:
            setattr(
                config.interests,
                rule_field,
                [str(k).strip() for k in value if str(k).strip()],
            )

    try:
        datetime.strptime(config.schedule.time, "%H:%M")
    except ValueError as exc:
        raise ConfigError(
            f"schedule.time must be HH:MM, got {config.schedule.time!r}"
        ) from exc

    config.output_dir = PROJECT_ROOT / config.digest.output_dir
    config.template_path = PROJECT_ROOT / config.digest.template
    config.log_dir = PROJECT_ROOT / config.log.dir
    config.state_path = PROJECT_ROOT / config.state.path
    config.feedback_path = PROJECT_ROOT / config.feedback.path
    if not config.template_path.exists():
        raise ConfigError(f"digest template not found: {config.template_path}")
    return config


def _stringify(value: object) -> object:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _stringify(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_stringify(item) for item in value]
    return value


def redacted_config_dict(config: Config) -> dict:
    """Config as a plain dict for display; secrets are never included, only presence."""
    data = _stringify(dataclasses.asdict(config))  # type: ignore[arg-type]
    api_key = os.environ.get(config.llm.api_key_env)
    data["llm"]["api_key"] = "set" if api_key else "not set"
    return data
