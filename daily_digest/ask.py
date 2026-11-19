"""F2 ask-this-item: the popup's chat drawer, answered by an LLM grounded ONLY
in that item's title + abstract + digest summary.

Two hard rules from the approved spec:
- SINGLE-SHOT budget: timeout 45s, 0 retries. The 90s×3 profile belongs to the
  unattended 09:00 run; an interactive drawer must not hang for ~5 minutes.
- The popup NEVER writes state.json (not even via util.load_json, which renames
  corrupt files — a write). build_popup_llm reads the session side-effect-free
  and falls back to an ephemeral ses_popup_* id; it never calls save_json.
"""

from __future__ import annotations

import dataclasses
import json
import os
import secrets

from daily_digest.config import Config
from daily_digest.ranking.llm import LlmClient
from daily_digest.util import LOG

ASK_TIMEOUT_SECONDS = 45.0
ASK_MAX_RETRIES = 0
ASK_DESCRIPTION_CHARS = 1200
ASK_SUMMARY_CHARS = 600

ASK_SYSTEM_PROMPT = (
    "You are the assistant inside a daily tech digest. The reader asks a question about ONE item. "
    "{profile_line}"
    "Ground your answer ONLY in the provided title, description and digest summary. If they do not "
    "contain the answer, say so plainly — never invent facts. "
    "Answer in the language of the question, at most 120 words, plain text."
)

OFFLINE_MESSAGE = (
    "Chưa cấu hình API key (OPENCODE_API_KEY trong .env) nên chưa hỏi được — "
    "digest vẫn đọc bình thường nhé."
)


def build_ask_messages(snapshot: dict, question: str, profile: str = "") -> list[dict]:
    profile_line = (
        f"Context about the reader's current work: {profile}\n" if profile else ""
    )
    system = ASK_SYSTEM_PROMPT.format(profile_line=profile_line)
    description = " ".join(str(snapshot.get("summary", "")).split())[
        :ASK_DESCRIPTION_CHARS
    ]
    digest_summary = " ".join(str(snapshot.get("llm_summary", "")).split())[
        :ASK_SUMMARY_CHARS
    ]
    user = (
        f"TITLE: {snapshot.get('title', '')}\n"
        f"SOURCE: {snapshot.get('source', '')}\n"
        f"DESCRIPTION: {description or '(no description)'}\n"
        f"DIGEST SUMMARY: {digest_summary or '(none)'}\n\n"
        f"QUESTION: {question}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def answer_question(snapshot: dict, question: str, chat, profile: str = "") -> str:
    """Total function: NEVER raises — offline/no-key/timeout all return a polite
    string so the JS Promise always resolves."""
    if chat is None:
        return OFFLINE_MESSAGE
    try:
        answer = str(chat(build_ask_messages(snapshot, question, profile))).strip()
        return answer or "(câu trả lời rỗng — thử hỏi lại nhé)"
    except Exception as exc:  # noqa: BLE001 — the drawer must never crash
        LOG.warning("ask failed: %s: %s", type(exc).__name__, exc)
        return f"Chưa hỏi được lúc này ({type(exc).__name__}). Thử lại sau nhé."


def _read_session_readonly(config: Config) -> str:
    """Side-effect-FREE state read for the popup process: never repairs, never
    renames (unlike util.load_json), never writes. Any error -> ''."""
    try:
        data = json.loads(config.state_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            value = data.get("llm_session")
            if isinstance(value, str) and value:
                return value
    except (OSError, json.JSONDecodeError):
        pass
    return ""


def build_popup_llm(config: Config) -> LlmClient | None:
    """The popup's ask client: same key + session, but the single-shot ask budget
    (45s, 0 retries) instead of the unattended-run profile. Read-only on state."""
    api_key = os.environ.get(config.llm.api_key_env)
    if not api_key:
        return None
    session_id = _read_session_readonly(config) or ("ses_popup_" + secrets.token_hex(8))
    ask_config = dataclasses.replace(
        config,
        llm=dataclasses.replace(
            config.llm,
            timeout_seconds=ASK_TIMEOUT_SECONDS,
            max_retries=ASK_MAX_RETRIES,
        ),
    )
    return LlmClient(ask_config, api_key, session_id)
