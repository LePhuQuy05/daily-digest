"""URL normalization and canonical ids, so the same story/paper is recognized across sources."""

from __future__ import annotations

import re
import urllib.parse

from daily_digest.model import Item

# New-style ids: 2611.21622 ; old-style ids: cs/0112017 ; both may carry a version suffix.
_ARXIV_PATTERNS = (
    re.compile(
        r"^https?://(?:www\.|export\.)?arxiv\.org/(?:abs|pdf)/"
        r"([0-9]{4}\.[0-9]{4,6}|[a-z\-]+(?:\.[a-z\-]+)?/[0-9]{7})(?:v[0-9]+)?/?",
        re.IGNORECASE,
    ),
    re.compile(
        r"^https?://(?:www\.)?huggingface\.co/papers/([0-9]{4}\.[0-9]{4,6})(?:v[0-9]+)?/?",
        re.IGNORECASE,
    ),
)


def canonical_arxiv_id(url: str) -> str | None:
    """Return the version-less arXiv id for arXiv/HF paper URLs, else None."""
    for pattern in _ARXIV_PATTERNS:
        match = pattern.match(url.strip())
        if match:
            return match.group(1).lower()
    return None


_ARXIV_IN_TEXT = re.compile(
    r"arxiv\.org/abs/([0-9]{4}\.[0-9]{4,6}|[a-z\-]+(?:\.[a-z\-]+)?/[0-9]{7})(?:v[0-9]+)?",
    re.IGNORECASE,
)


def find_arxiv_id(text: str) -> str | None:
    """Find an arXiv id anywhere inside free text/HTML (e.g. an RSS description blob)."""
    match = _ARXIV_IN_TEXT.search(text)
    return match.group(1).lower() if match else None


def normalize_url(url: str) -> str:
    """Lowercase scheme/host, drop utm_* params, strip trailing slash — for stable comparison only."""
    try:
        parts = urllib.parse.urlsplit(url.strip())
    except ValueError:
        return url.strip().lower()
    query = urllib.parse.urlencode(
        [
            (k, v)
            for k, v in urllib.parse.parse_qsl(parts.query)
            if not k.lower().startswith("utm_")
        ]
    )
    path = parts.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return urllib.parse.urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), path, query, "")
    )


def safe_href(url: str) -> str:
    """Only http(s) links are allowed in the digest; anything else renders as '#'."""
    scheme = urllib.parse.urlsplit(url.strip()).scheme.lower()
    return url if scheme in ("http", "https") else "#"


def item_uid(item: Item) -> str:
    """Stable cross-source uid: arXiv id when known, else source-specific, else normalized URL."""
    arxiv_id = canonical_arxiv_id(item.url)
    if arxiv_id:
        return f"arxiv:{arxiv_id}"
    if item.source == "hn" and item.id.startswith("hn:"):
        return f"hn:{item.id[3:]}"
    return f"url:{normalize_url(item.url)}"
