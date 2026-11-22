"""Reader-facing source labels shared by ranking, rendering and the heuristic fallback."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from daily_digest.config import Config

SOURCE_LABELS: dict[str, str] = {
    "hn": "Hacker News",
    "arxiv": "arXiv",
    "hf_papers": "HF Papers",
    "emergentmind": "Emergent Mind",
    "alphaxiv": "alphaXiv",
    "openai_news": "OpenAI",
    "deepmind_blog": "Google DeepMind",
    "google_ai_blog": "Google AI",
    "google_research": "Google Research",
    "microsoft_research": "Microsoft Research",
    "huggingface_blog": "Hugging Face",
    "epoch_ai": "Epoch AI",
    "apple_ml": "Apple ML",
    "ai2_blog": "Ai2",
    "vllm_blog": "vLLM",
    "pytorch_blog": "PyTorch",
    "meta_engineering": "Meta Engineering",
    "modal_blog": "Modal",
    "alignment_forum": "Alignment Forum",
    "metr": "METR",
    "vals_ai": "Vals AI",
    "transformer_circuits": "Transformer Circuits",
    "the_verge_ai": "The Verge",
    "ieee_spectrum_ai": "IEEE Spectrum",
    "ars_technica": "Ars Technica",
    "mit_tech_review": "MIT Technology Review",
    "simon_willison": "Simon Willison",
    "interconnects": "Interconnects",
    "import_ai": "Import AI",
    "gh_vllm": "vLLM",
    "gh_ollama": "Ollama",
    "gh_transformers": "Transformers",
    "gh_openwebui": "Open WebUI",
    "gh_sglang": "SGLang",
    "gh_unsloth": "Unsloth",
    "gh_comfyui": "ComfyUI",
}


def labels_for(config: Config) -> dict[str, str]:
    """Default labels plus any custom feed labels from config."""
    labels = dict(SOURCE_LABELS)
    feeds = getattr(getattr(config, "sources", None), "feeds", None)
    for entry in getattr(feeds, "entries", []) or []:
        if isinstance(entry, dict):
            name = str(entry.get("name") or "")
            label = str(entry.get("label") or "")
        else:
            name = str(getattr(entry, "name", ""))
            label = str(getattr(entry, "label", ""))
        if name and label:
            labels[name] = label
    return labels
