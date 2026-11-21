"""vi/en/ja locale catalogs, resolution, dates and CJK text helpers."""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING, Literal

from daily_digest.util import LOG

if TYPE_CHECKING:  # pragma: no cover - typing only
    from daily_digest.config import Config

Locale = Literal["vi", "en", "ja"]
SUPPORTED_LOCALES: tuple[Locale, ...] = ("vi", "en", "ja")
DEFAULT_LOCALE: Locale = "vi"

LOCALE_LABEL: dict[Locale, str] = {
    "vi": "Tiếng Việt",
    "en": "English",
    "ja": "日本語",
}
PROMPT_LANGUAGE: dict[Locale, str] = {
    "vi": "Vietnamese",
    "en": "English",
    "ja": "Japanese",
}
_WEEKDAYS: dict[Locale, tuple[str, ...]] = {
    "vi": ("THỨ HAI", "THỨ BA", "THỨ TƯ", "THỨ NĂM", "THỨ SÁU", "THỨ BẢY", "CHỦ NHẬT"),
    "en": (
        "MONDAY",
        "TUESDAY",
        "WEDNESDAY",
        "THURSDAY",
        "FRIDAY",
        "SATURDAY",
        "SUNDAY",
    ),
    "ja": ("月", "火", "水", "木", "金", "土", "日"),
}
_JA_CLOSERS = "」』）】"
_JA_END = "。！？"
_FULLWIDTH = str.maketrans(
    "［］０１２３４５６７８９",
    "[]0123456789",
)


class LocaleError(ValueError):
    """Invalid locale code."""


_VI: dict[str, str] = {
    "edition": "BẢN TIN AI",
    "masthead_saved": "Đã lưu",
    "masthead_saved_title": "Xem tất cả bài đã lưu",
    "masthead_refresh": "Tìm bài mới",
    "masthead_refresh_title": "Tìm các bài mới chưa từng hiển thị",
    "theme_toggle": "Đổi giao diện sáng/tối",
    "nav_aria": "Chuyên mục",
    "size_trigger_title": "Đổi số bài trong bản tin",
    "nav_overview": "Tổng hợp",
    "nav_papers": "Nghiên cứu",
    "nav_tech": "Công nghệ",
    "nav_tools": "Công cụ",
    "nav_pinned": "Nhìn lại",
    "dateline_stories": "{n} câu chuyện",
    "dateline_editor": "Biên tập: {name}",
    "mode_demo": "demo",
    "mode_empty": "bản tin trống",
    "mode_heuristic": "heuristic",
    "degraded": "Bản tin chạy ở chế độ suy giảm.",
    "degraded_sources": "Nguồn không khả dụng: {sources}.",
    "degraded_details": "Chi tiết trong {path}.",
    "notice_muted_all": "interests.mute đã lọc mất toàn bộ mục hôm nay — kiểm tra lại danh sách mute ({n} mục bị lọc).",
    "empty_none": "Hôm nay không có mục nào.",
    "section_papers": "Nghiên cứu",
    "section_tech_news": "Công nghệ",
    "section_tools_releases": "Công cụ",
    "section_count": "{n} bài",
    "section_above": "{n} ở trên",
    "section_empty": "Hôm nay không có mục nào trong nhóm này.",
    "section_lead_above": "Bài chính ở trên.",
    "most_read_title": "Đọc nhiều",
    "pinned_title": "Nhìn lại",
    "pinned_older": "+{n} cũ hơn",
    "source_prefix": "Nguồn:",
    "heuristic_matches": "khớp: {topics}",
    "heuristic_trending_hf": "đang trending trên HF Papers",
    "heuristic_trending_alphaxiv": "nổi bật trên alphaXiv",
    "heuristic_trending_em": "trending trên mạng xã hội (Emergent Mind)",
    "heuristic_new_arxiv": "arXiv mới {id}",
    "heuristic_hn": "trang nhất HN",
    "heuristic_release": "bản phát hành mới",
    "heuristic_via": "qua {label}",
    "heuristic_top": "bài nổi bật hôm nay",
    "heuristic_overview": "{total} mục hôm nay: {papers} bài báo · {news} tin công nghệ · {tools} công cụ. Chủ đề nổi bật: {topics}.",
    "demo_notice": "Chế độ demo: dữ liệu mẫu, không cần mạng hay API key.",
    "story_kicker": "CÂU CHUYỆN CHÍNH",
    "story_points": "{n} điểm",
    "story_citations": "{n} trích dẫn",
    "story_new": "MỚI",
    "story_save": "Lưu",
    "story_saved": "Đã lưu",
    "story_save_title": "Giữ lại trong mục Nhìn lại",
    "story_save_aria": "Lưu mục này vào Nhìn lại",
    "story_unsave_title": "Đọc xong, bỏ khỏi Nhìn lại",
    "story_unsave_aria": "Đọc xong, bỏ khỏi Nhìn lại",
    "story_done": "Đọc xong",
    "story_like_title": "Digest này nên có nhiều bài thế này hơn",
    "story_like_aria": "Thích mục này",
    "story_dislike_title": "Bớt loại này ra",
    "story_dislike_aria": "Không thích mục này",
    "story_ask_summary": "Hỏi biên tập",
    "story_ask_placeholder": "Hỏi thêm về mục này… (Ctrl+Enter)",
    "story_ask_aria": "Nhập câu hỏi về mục này",
    "story_ask_button": "Hỏi",
    "story_ask_question_aria": "Hỏi về mục này",
    "overview_label": "Tổng hợp hôm nay",
    "overview_title": "Trong ngày",
    "overview_rest": "Còn lại hôm nay: ",
    "overview_story_n": "Bài {n}",
    "overview_takeaway_marker": "Điểm cần nhớ:",
    "overview_jump_aria": "Chuyển đến bài: {title}",
    "summary_ai_label": "AI SUMMARY",
    "saved_title": "Đã lưu",
    "saved_empty": "Chưa có bài nào được lưu.",
    "saved_load_error": "Không tải được danh sách đã lưu.",
    "saved_close": "Đóng",
    "saved_no_title": "(không có tiêu đề)",
    "settings_title": "Cài đặt",
    "settings_change": "Đổi",
    "settings_help": "Chọn từ {min} đến {max} bài. Mặc định là {default}.",
    "settings_current": "Bản này: {n} câu chuyện.",
    "settings_size_group": "Số bài",
    "settings_language": "Ngôn ngữ",
    "settings_language_help": "Đổi ngôn ngữ sẽ chạy lại editor + writer.",
    "settings_drift_warning": "Đổi ngôn ngữ sẽ chạy lại và có thể chọn bộ bài khác.",
    "settings_archived": "Bản lưu trữ chỉ xem; không thể đổi cài đặt.",
    "settings_no_key": "Không có API key — lần chạy lại sẽ dùng xếp hạng heuristic.",
    "settings_apply": "Áp dụng",
    "settings_reset": "Đặt lại",
    "settings_close": "Đóng",
    "settings_saving": "Đang lưu…",
    "settings_updating": "Đang cập nhật…",
    "settings_saved": "Đã lưu. Lần chạy tới sẽ dùng {n} bài.",
    "settings_reset_done": "Đã đặt lại về {n} bài.",
    "settings_error_read": "Không đọc được cấu hình.",
    "settings_error_save": "Không lưu được cài đặt.",
    "settings_error_reset": "Không đặt lại được.",
    "settings_minus": "Giảm số bài",
    "settings_plus": "Tăng số bài",
    "settings_value_aria": "Số bài",
    "undo_saved": "Đã bỏ lưu.",
    "undo_button": "Hoàn tác",
    "undo_error": "Không hoàn tác được.",
    "refresh_searching": "Đang tìm bài mới…",
    "refresh_sent": "Đã gửi yêu cầu làm mới.",
    "refresh_retry": "Thử lại",
    "refresh_error": "Không làm mới được.",
    "ask_empty": "Bạn chưa nhập câu hỏi.",
    "ask_error": "Chưa hỏi được lúc này. Thử lại sau nhé.",
    "ask_offline": "Chưa cấu hình API key nên chưa hỏi được.",
    "ask_no_answer": "Chưa có câu trả lời.",
    "toast_body": "{n} mục đã sẵn sàng.",
    "footer": "Tạo bởi daily-digest · đổi model trong llm.model của config.yaml · các bản cũ lưu trong output/.",
}

_EN: dict[str, str] = {
    "edition": "AI BRIEFING",
    "masthead_saved": "Saved",
    "masthead_saved_title": "View all saved articles",
    "masthead_refresh": "Find new",
    "masthead_refresh_title": "Find new items not shown before",
    "theme_toggle": "Toggle light/dark theme",
    "nav_aria": "Sections",
    "size_trigger_title": "Change the number of items",
    "nav_overview": "Overview",
    "nav_papers": "Research",
    "nav_tech": "Tech",
    "nav_tools": "Tools",
    "nav_pinned": "Saved",
    "dateline_stories": "{n} stories",
    "dateline_editor": "Edited by: {name}",
    "mode_demo": "demo",
    "mode_empty": "empty digest",
    "mode_heuristic": "heuristic",
    "degraded": "This digest ran in degraded mode.",
    "degraded_sources": "Unavailable source(s): {sources}.",
    "degraded_details": "Details in {path}.",
    "notice_muted_all": "interests.mute removed every fresh item today — review the mute list ({n} removed).",
    "empty_none": "No items today.",
    "section_papers": "Research",
    "section_tech_news": "Tech News",
    "section_tools_releases": "Tools & Releases",
    "section_count": "{n} stories",
    "section_above": "{n} above",
    "section_empty": "No items in this section today.",
    "section_lead_above": "Lead story above.",
    "most_read_title": "Most read",
    "pinned_title": "Saved",
    "pinned_older": "+{n} older",
    "source_prefix": "Sources:",
    "heuristic_matches": "matches: {topics}",
    "heuristic_trending_hf": "trending on HF Papers",
    "heuristic_trending_alphaxiv": "hot on alphaXiv",
    "heuristic_trending_em": "trending across social media (Emergent Mind)",
    "heuristic_new_arxiv": "new arXiv {id}",
    "heuristic_hn": "HN front page",
    "heuristic_release": "new release",
    "heuristic_via": "via {label}",
    "heuristic_top": "top story today",
    "heuristic_overview": "{total} items today: {papers} papers · {news} tech news · {tools} tools. Top themes: {topics}.",
    "demo_notice": "Demo mode: bundled fixtures, no network or API key.",
    "story_kicker": "TOP STORY",
    "story_points": "{n} points",
    "story_citations": "{n} citations",
    "story_new": "NEW",
    "story_save": "Save",
    "story_saved": "Saved",
    "story_save_title": "Keep this in Saved",
    "story_save_aria": "Save this item to Saved",
    "story_unsave_title": "Done reading, remove from Saved",
    "story_unsave_aria": "Done reading, remove from Saved",
    "story_done": "Done",
    "story_like_title": "Show me more like this",
    "story_like_aria": "Like this item",
    "story_dislike_title": "Show me less like this",
    "story_dislike_aria": "Dislike this item",
    "story_ask_summary": "Ask the editor",
    "story_ask_placeholder": "Ask about this item… (Ctrl+Enter)",
    "story_ask_aria": "Enter a question about this item",
    "story_ask_button": "Ask",
    "story_ask_question_aria": "Ask about this item",
    "overview_label": "Today's overview",
    "overview_title": "Today's themes",
    "overview_rest": "Remaining today: ",
    "overview_story_n": "Item {n}",
    "overview_takeaway_marker": "Key takeaway:",
    "overview_jump_aria": "Go to article: {title}",
    "summary_ai_label": "AI SUMMARY",
    "saved_title": "Saved",
    "saved_empty": "No saved articles yet.",
    "saved_load_error": "Could not load saved articles.",
    "saved_close": "Close",
    "saved_no_title": "(untitled)",
    "settings_title": "Settings",
    "settings_change": "Change",
    "settings_help": "Choose {min}–{max} items. Default: {default}.",
    "settings_current": "This edition: {n} stories.",
    "settings_size_group": "Item count",
    "settings_language": "Language",
    "settings_language_help": "Changing language reruns the editor + writer.",
    "settings_drift_warning": "Changing language reruns the pipeline and may select a different set of stories.",
    "settings_archived": "Archived digests are read-only.",
    "settings_no_key": "No API key — the next run will use heuristic ranking.",
    "settings_apply": "Apply",
    "settings_reset": "Reset",
    "settings_close": "Close",
    "settings_saving": "Saving…",
    "settings_updating": "Updating…",
    "settings_saved": "Saved. The next run will use {n} items.",
    "settings_reset_done": "Reset to {n} items.",
    "settings_error_read": "Could not read settings.",
    "settings_error_save": "Could not save settings.",
    "settings_error_reset": "Could not reset settings.",
    "settings_minus": "Decrease item count",
    "settings_plus": "Increase item count",
    "settings_value_aria": "Item count",
    "undo_saved": "Removed from Saved.",
    "undo_button": "Undo",
    "undo_error": "Could not undo.",
    "refresh_searching": "Looking for new items…",
    "refresh_sent": "Refresh requested.",
    "refresh_retry": "Try again",
    "refresh_error": "Could not refresh.",
    "ask_empty": "Please enter a question.",
    "ask_error": "Could not answer right now. Try again later.",
    "ask_offline": "Add an API key to ask questions.",
    "ask_no_answer": "No answer yet.",
    "toast_body": "{n} items are ready.",
    "footer": "Generated by daily-digest · edit llm.model in config.yaml · old digests are archived in output/.",
}

_JA: dict[str, str] = {
    "edition": "AIニュース",
    "masthead_saved": "保存済み",
    "masthead_saved_title": "保存した記事をすべて見る",
    "masthead_refresh": "新着を探す",
    "masthead_refresh_title": "まだ表示していない新着を探す",
    "theme_toggle": "ライト/ダークを切り替え",
    "nav_aria": "セクション",
    "size_trigger_title": "記事数を変更",
    "nav_overview": "まとめ",
    "nav_papers": "研究",
    "nav_tech": "テック",
    "nav_tools": "ツール",
    "nav_pinned": "振り返り",
    "dateline_stories": "{n}件の記事",
    "dateline_editor": "編集: {name}",
    "mode_demo": "デモ",
    "mode_empty": "空のダイジェスト",
    "mode_heuristic": "ヒューリスティック",
    "degraded": "このダイジェストは縮退モードで実行されました。",
    "degraded_sources": "利用できないソース: {sources}。",
    "degraded_details": "詳細: {path}。",
    "notice_muted_all": "interests.mute により本日の項目がすべて除外されました（{n}件）。ミュート設定を確認してください。",
    "empty_none": "本日の項目はありません。",
    "section_papers": "論文",
    "section_tech_news": "テックニュース",
    "section_tools_releases": "ツール・リリース",
    "section_count": "{n}件",
    "section_above": "他{n}件",
    "section_empty": "このセクションに本日の項目はありません。",
    "section_lead_above": "主要記事は上にあります。",
    "most_read_title": "よく読む",
    "pinned_title": "振り返り",
    "pinned_older": "他{n}件",
    "source_prefix": "ソース:",
    "heuristic_matches": "一致: {topics}",
    "heuristic_trending_hf": "HF Papersでトレンド",
    "heuristic_trending_alphaxiv": "alphaXivで注目",
    "heuristic_trending_em": "SNSでトレンド (Emergent Mind)",
    "heuristic_new_arxiv": "新着arXiv {id}",
    "heuristic_hn": "HNトップ",
    "heuristic_release": "新リリース",
    "heuristic_via": "{label}経由",
    "heuristic_top": "本日のトップ記事",
    "heuristic_overview": "本日{total}件: 論文{papers}件 · テックニュース{news}件 · ツール{tools}件。主なテーマ: {topics}。",
    "demo_notice": "デモモード: 同梱データを使用。ネットワークとAPIキーは不要です。",
    "story_kicker": "トップ記事",
    "story_points": "{n}ポイント",
    "story_citations": "{n}件の引用",
    "story_new": "新着",
    "story_save": "保存",
    "story_saved": "保存済み",
    "story_save_title": "振り返りに保存",
    "story_save_aria": "この記事を振り返りに保存",
    "story_unsave_title": "読了して振り返りから外す",
    "story_unsave_aria": "読了して振り返りから外す",
    "story_done": "読了",
    "story_like_title": "この種類をもっと表示",
    "story_like_aria": "この記事が好き",
    "story_dislike_title": "この種類を減らす",
    "story_dislike_aria": "この記事が好きではない",
    "story_ask_summary": "編集者に質問",
    "story_ask_placeholder": "この記事について質問… (Ctrl+Enter)",
    "story_ask_aria": "この記事について質問を入力",
    "story_ask_button": "質問",
    "story_ask_question_aria": "この記事について質問",
    "overview_label": "今日のまとめ",
    "overview_title": "今日の動き",
    "overview_rest": "本日の残り: ",
    "overview_story_n": "記事 {n}",
    "overview_takeaway_marker": "要点:",
    "overview_jump_aria": "記事へ移動: {title}",
    "summary_ai_label": "AI要約",
    "saved_title": "保存済み",
    "saved_empty": "保存した記事はありません。",
    "saved_load_error": "保存記事を読み込めませんでした。",
    "saved_close": "閉じる",
    "saved_no_title": "（タイトルなし）",
    "settings_title": "設定",
    "settings_change": "変更",
    "settings_help": "{min}〜{max}件から選択。既定は{default}件です。",
    "settings_current": "この版: {n}件の記事。",
    "settings_size_group": "記事数",
    "settings_language": "言語",
    "settings_language_help": "言語を変更すると editor + writer を再実行します。",
    "settings_drift_warning": "言語を変更すると再実行され、記事の選択が変わる場合があります。",
    "settings_archived": "アーカイブ版は閲覧のみです。",
    "settings_no_key": "APIキーがないため、次回はヒューリスティックで実行されます。",
    "settings_apply": "適用",
    "settings_reset": "リセット",
    "settings_close": "閉じる",
    "settings_saving": "保存中…",
    "settings_updating": "更新中…",
    "settings_saved": "保存しました。次回は{n}件を使用します。",
    "settings_reset_done": "{n}件にリセットしました。",
    "settings_error_read": "設定を読み込めませんでした。",
    "settings_error_save": "設定を保存できませんでした。",
    "settings_error_reset": "設定をリセットできませんでした。",
    "settings_minus": "記事数を減らす",
    "settings_plus": "記事数を増やす",
    "settings_value_aria": "記事数",
    "undo_saved": "保存を取り消しました。",
    "undo_button": "元に戻す",
    "undo_error": "元に戻せませんでした。",
    "refresh_searching": "新着を検索中…",
    "refresh_sent": "更新を開始しました。",
    "refresh_retry": "再試行",
    "refresh_error": "更新できませんでした。",
    "ask_empty": "質問を入力してください。",
    "ask_error": "現在回答できません。後でもう一度お試しください。",
    "ask_offline": "APIキーがないため質問できません。",
    "ask_no_answer": "回答はまだありません。",
    "toast_body": "{n}件の記事の準備ができました。",
    "footer": "daily-digest による生成 · モデルは config.yaml の llm.model で変更 · 過去の版は output/ に保存。",
}

_CATALOG: dict[Locale, dict[str, str]] = {"vi": _VI, "en": _EN, "ja": _JA}
_MISSING: set[tuple[str, str]] = set()


def normalize_locale(value: object) -> Locale | None:
    if not isinstance(value, str):
        return None
    raw = value.strip().lower().replace("_", "-")
    if not raw:
        return None
    base = raw.split("-", 1)[0]
    return base if base in SUPPORTED_LOCALES else None  # type: ignore[return-value]


def require_locale(value: object) -> Locale:
    locale = normalize_locale(value)
    if locale is None:
        raise LocaleError(f"unsupported locale: {value!r}")
    return locale


def resolve_locale(
    config: Config, preferences: dict, override: str | None = None
) -> Locale:
    if override is not None:
        return require_locale(override)
    if isinstance(preferences, dict):
        stored = preferences.get("language")
        if stored is not None:
            locale = normalize_locale(stored)
            if locale is not None:
                return locale
            LOG.warning("preferences.language ignored: unsupported %r", stored)
    legacy = getattr(config.llm, "overview_language", "")
    locale = normalize_locale(legacy)
    if locale is not None:
        if locale != DEFAULT_LOCALE:
            LOG.info(
                "using legacy llm.overview_language=%s as the initial locale; "
                "save a language preference to make it explicit",
                locale,
            )
        return locale
    if legacy:
        LOG.warning("llm.overview_language ignored: unsupported %r", legacy)
    return DEFAULT_LOCALE


def _fallback_chain(locale: str) -> tuple[Locale, ...]:
    current = normalize_locale(locale) or DEFAULT_LOCALE
    if current == "vi":
        return ("vi",)
    if current == "en":
        return ("en", "vi")
    return ("ja", "en", "vi")


def t(locale: str, key: str, **kwargs) -> str:
    for fallback in _fallback_chain(locale):
        value = _CATALOG[fallback].get(key)
        if value is not None:
            try:
                return value.format(**kwargs)
            except (KeyError, ValueError):
                return value
    if (locale, key) not in _MISSING:
        _MISSING.add((locale, key))
        LOG.warning("missing i18n key %r for locale %s", key, locale)
    return key


def locale_strings(locale: str) -> dict[str, str]:
    keys: set[str] = set()
    for fallback in _fallback_chain(locale):
        keys.update(_CATALOG[fallback])
    return {key: t(locale, key) for key in keys}


def js_messages(locale: str) -> dict[str, str]:
    return locale_strings(locale)


def format_date_long(date_value: str, locale: str) -> str:
    try:
        parsed = datetime.strptime(date_value, "%Y-%m-%d")
    except (TypeError, ValueError):
        return date_value
    loc = normalize_locale(locale) or DEFAULT_LOCALE
    weekday = _WEEKDAYS[loc][parsed.weekday()]
    if loc == "ja":
        return f"{parsed.year}年{parsed.month}月{parsed.day}日（{weekday}）"
    return f"{weekday}, {parsed:%d.%m.%Y}"


def format_short_date(value: datetime | None, locale: str) -> str:
    if not isinstance(value, datetime):
        return ""
    loc = normalize_locale(locale) or DEFAULT_LOCALE
    if loc == "ja":
        return f"{value.year}年{value.month}月{value.day}日"
    return value.strftime("%d.%m.%Y")


def section_title(section: str, locale: str) -> str:
    return t(locale, f"section_{section}")


def split_sentences(text: str, locale: str) -> list[str]:
    """Split prose into points; blank lines are the primary boundary."""
    cleaned = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = [
        part.strip() for part in re.split(r"\n\s*\n", cleaned) if part.strip()
    ]
    if not paragraphs:
        return []
    loc = normalize_locale(locale) or DEFAULT_LOCALE
    points: list[str] = []
    for paragraph in paragraphs:
        if loc == "ja":
            joined = "".join(part.strip() for part in paragraph.splitlines())
            points.extend(_split_ja(joined))
        else:
            joined = " ".join(part.strip() for part in paragraph.splitlines())
            points.extend(
                part.strip()
                for part in re.split(r"(?<=[.!?])\s+", joined)
                if part.strip()
            )
    return points


def _split_ja(text: str) -> list[str]:
    points: list[str] = []
    start = 0
    index = 0
    while index < len(text):
        if text[index] not in _JA_END:
            index += 1
            continue
        end = index + 1
        while end < len(text) and text[end] in _JA_END:
            end += 1
        while end < len(text) and text[end] in _JA_CLOSERS:
            end += 1
        part = text[start:end].strip()
        if part:
            points.append(part)
        start = end
        index = end
    tail = text[start:].strip()
    if tail:
        points.append(tail)
    return points


def normalize_markers(text: str) -> str:
    return (text or "").translate(_FULLWIDTH)


def _strip_partial_marker(text: str) -> str:
    last_open = text.rfind("[[")
    last_close = text.rfind("]]")
    if last_open > last_close:
        return text[:last_open].rstrip()
    if text.endswith("["):
        return text[:-1].rstrip()
    return text


def truncate_overview(text: str, max_chars: int, locale: str) -> str:
    cleaned = normalize_markers(text).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    cut = cleaned[:max_chars]
    loc = normalize_locale(locale) or DEFAULT_LOCALE
    if loc == "ja":
        boundary = max(cut.rfind(ch) for ch in _JA_END)
        if boundary > max_chars // 2:
            end = boundary + 1
            while end < len(cut) and cut[end] in _JA_CLOSERS:
                end += 1
            cut = cut[:end]
        else:
            cut = cut.rstrip("。、！？ ")
    else:
        blank = cut.rfind("\n\n")
        if blank > max_chars // 2:
            cut = cut[:blank]
        else:
            sentence = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
            if sentence > max_chars // 2:
                cut = cut[: sentence + 1]
            else:
                last_space = cut.rfind(" ")
                if last_space > max_chars // 2:
                    cut = cut[:last_space]
    cut = _strip_partial_marker(cut)
    return cut.rstrip(" ,;:.-。、！？") + "…"


def takeaway_marker(locale: str) -> str:
    return t(locale, "overview_takeaway_marker")


_KANA_RE = re.compile(r"[\u3040-\u30ff\u31f0-\u31ff]")


def has_kana(text: str) -> bool:
    """True when text contains hiragana or katakana."""
    return bool(_KANA_RE.search(text or ""))


def fails_kana_gate(text: str, locale: str) -> bool:
    """Reject long Japanese output that contains no kana at all.

    Technical Latin terms are allowed as long as the sentence also contains
    Japanese kana; the gate only catches accidentally-English output.
    """
    if (normalize_locale(locale) or "vi") != "ja":
        return False
    cleaned = (text or "").strip()
    return len(cleaned) > 20 and not has_kana(cleaned)
