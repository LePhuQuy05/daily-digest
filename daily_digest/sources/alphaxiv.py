"""alphaXiv hot feed via the official MCP server (https://api.alphaxiv.org/mcp/v1).

The Hot feed (30-day window, app order) is an ORDERED LIST of bare arXiv ids —
that is the community-attention signal. Schema verified live 2026-11-19 with
tools/list: get_hot_feed takes only `limit` (1-200) and returns
{"papers": [{"universal_paper_id": ...}]}; no titles/upvotes in the response.

So the fetch is two steps:
  1. MCP: initialize -> notifications/initialized -> tools/call(get_hot_feed, {limit})
  2. arXiv API: one batched id_list query resolving titles/abstracts/dates.

Speaks MCP Streamable HTTP directly (JSON-RPC over POST) — no MCP SDK dependency.
Keyless skip: without ALPHAXIV_API_KEY the fetcher returns [] (one INFO log), so
the digest runs fine until you paste a free key into .env.
"""

from __future__ import annotations

import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime

import httpx

from daily_digest import __version__
from daily_digest.config import AlphaxivCfg
from daily_digest.model import Item
from daily_digest.normalize import canonical_arxiv_id, find_arxiv_id
from daily_digest.util import LOG

ALPHAXIV_MCP_URL = "https://api.alphaxiv.org/mcp/v1"
ARXIV_API_URL = "https://export.arxiv.org/api/query"
_ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom"}
_USER_AGENT = "daily-digest/0.1 (personal research digest tool)"

_MCP_PROTOCOL_VERSION = "2025-06-18"

_ID_KEYS = ("universal_paper_id", "arxiv_id", "arxivId", "paper_id", "paperId", "id")
_BARE_ARXIV_ID = re.compile(r"\d{4}\.\d{4,6}")


class AlphaxivError(Exception):
    """alphaXiv fetch failed in a way worth surfacing (auth, shape, transport)."""


def _parse_sse_or_json(response: httpx.Response) -> dict:
    """MCP servers may answer with application/json or an SSE stream; handle both."""
    content_type = (response.headers.get("content-type") or "").lower()
    if "text/event-stream" in content_type:
        payload: dict | None = None
        for line in response.text.splitlines():
            if not line.startswith("data:"):
                continue
            chunk = line[len("data:") :].strip()
            if not chunk:
                continue
            try:
                candidate = json.loads(chunk)
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict) and (
                "result" in candidate or "error" in candidate
            ):
                payload = candidate
        if payload is None:
            raise AlphaxivError("no JSON-RPC payload in the SSE stream")
        return payload
    try:
        return response.json()
    except ValueError as exc:
        raise AlphaxivError(f"non-JSON MCP response: {response.text[:200]}") from exc


def _post_rpc(
    client: httpx.Client, api_key: str, body: dict, session_id: str | None
) -> tuple[dict | None, str | None]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {api_key}",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    response = client.post(ALPHAXIV_MCP_URL, headers=headers, json=body)
    if response.status_code in (401, 403):
        raise AlphaxivError(
            f"HTTP {response.status_code} — check the alphaXiv API key in .env "
            f"({response.text[:120]})"
        )
    response.raise_for_status()
    new_session = response.headers.get("Mcp-Session-Id") or session_id
    if not response.content:  # notifications get empty 202s
        return None, new_session
    return _parse_sse_or_json(response), new_session


def _iter_feed_records(payload: object):
    """Walk whatever get_hot_feed returned and yield dict records."""
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return
    if isinstance(payload, dict):
        if "result" in payload and isinstance(payload["result"], (dict, list)):
            yield from _iter_feed_records(payload["result"])
            return
        if "structuredContent" in payload and isinstance(
            payload["structuredContent"], (dict, list)
        ):
            yield from _iter_feed_records(payload["structuredContent"])
        for content in payload.get("content", []) or []:
            if isinstance(content, dict) and content.get("type") == "text":
                yield from _iter_feed_records(str(content.get("text", "")))
        for key in ("papers", "results", "feed", "items", "data"):
            if key in payload and isinstance(payload[key], list):
                for entry in payload[key]:
                    if isinstance(entry, dict):
                        yield entry
        return
    if isinstance(payload, list):
        for entry in payload:
            if isinstance(entry, dict):
                yield entry


def _extract_paper_id(record: dict) -> str | None:
    for key in _ID_KEYS:
        value = record.get(key)
        if isinstance(value, str):
            if "arxiv.org" in value:
                found = find_arxiv_id(value)
                if found:
                    return found
            candidate = value.strip().lower().removeprefix("arxiv:")
            if _BARE_ARXIV_ID.fullmatch(candidate):
                return candidate
    for value in record.values():  # last resort: any arxiv.org/abs URL in the record
        if isinstance(value, str):
            found = find_arxiv_id(value)
            if found:
                return found
    return None


def hot_feed_ids(payload: object) -> list[str]:
    """Ordered, de-duplicated bare arXiv ids from a get_hot_feed response."""
    ids: list[str] = []
    for record in _iter_feed_records(payload):
        arxiv_id = _extract_paper_id(record)
        if arxiv_id and arxiv_id not in ids:
            ids.append(arxiv_id)
    return ids


def fetch_arxiv_metadata(client: httpx.Client, arxiv_ids: list[str]) -> dict[str, dict]:
    """One batched arXiv API call (id_list) resolving title/summary/published per id."""
    response = client.get(
        ARXIV_API_URL,
        params={"id_list": ",".join(arxiv_ids), "max_results": len(arxiv_ids)},
        headers={"User-Agent": _USER_AGENT},
    )
    response.raise_for_status()
    root = ET.fromstring(response.text)
    metadata: dict[str, dict] = {}
    for entry in root.findall("atom:entry", _ARXIV_NS):
        entry_id = entry.findtext("atom:id", namespaces=_ARXIV_NS) or ""
        arxiv_id = canonical_arxiv_id(entry_id.strip())
        if not arxiv_id:
            continue
        published: datetime | None = None
        raw_published = entry.findtext("atom:published", namespaces=_ARXIV_NS)
        if raw_published:
            try:
                published = datetime.fromisoformat(raw_published.replace("Z", "+00:00"))
            except ValueError:
                published = None
        metadata[arxiv_id] = {
            "title": " ".join(
                (entry.findtext("atom:title", namespaces=_ARXIV_NS) or "").split()
            ),
            "summary": " ".join(
                (entry.findtext("atom:summary", namespaces=_ARXIV_NS) or "").split()
            )[:1500],
            "published": published,
        }
    return metadata


def fetch_alphaxiv(client: httpx.Client, cfg: AlphaxivCfg) -> list[Item]:
    api_key = os.environ.get(cfg.api_key_env)
    if not api_key:
        LOG.info(
            "alphaXiv key not set (env %s) — skipping; add it to .env to enable",
            cfg.api_key_env,
        )
        return []

    limit = max(1, min(200, cfg.max_items))  # tool schema: limit 1-200
    init_body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": _MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "daily-digest", "version": __version__},
        },
    }
    init_response, session_id = _post_rpc(client, api_key, init_body, None)
    if not init_response or "result" not in init_response:
        raise AlphaxivError(
            f"unexpected initialize response: {str(init_response)[:200]}"
        )

    _post_rpc(
        client,
        api_key,
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        session_id,
    )

    call_response, _ = _post_rpc(
        client,
        api_key,
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "get_hot_feed", "arguments": {"limit": limit}},
        },
        session_id,
    )
    if not call_response or "error" in call_response:
        error = (call_response or {}).get("error")
        raise AlphaxivError(f"get_hot_feed failed: {error or str(call_response)[:200]}")
    result = call_response.get("result", {})

    ids = hot_feed_ids(result)[:limit]
    if not ids:
        # The tool answered but nothing parsed: the response shape likely changed.
        # Surface it (SourceError -> degraded digest + log) instead of silently
        # contributing nothing forever.
        raise AlphaxivError(
            f"get_hot_feed answered but no paper ids parsed — response shape may have "
            f"changed: {str(result)[:300]}"
        )

    try:
        metadata = fetch_arxiv_metadata(client, ids)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            LOG.warning("alphaXiv metadata rate-limited (arXiv 429); skipping this run")
            return []
        raise
    except httpx.TimeoutException:
        LOG.warning("alphaXiv metadata timed out; skipping this run")
        return []
    items = [
        Item(
            id=f"arxiv:{arxiv_id}",
            title=metadata[arxiv_id]["title"],
            url=f"https://arxiv.org/abs/{arxiv_id}",
            source="alphaxiv",
            points=None,  # the signal is being IN the hot feed (and its order)
            published=metadata[arxiv_id]["published"],
            summary=metadata[arxiv_id]["summary"],
        )
        for arxiv_id in ids
        if arxiv_id in metadata and metadata[arxiv_id]["title"]
    ]
    unresolved = len(ids) - len(items)
    if unresolved:
        LOG.debug(
            "alphaXiv: %d hot ids did not resolve on arXiv (link blogs?)", unresolved
        )
    if not items:
        raise AlphaxivError(
            "hot feed ids could not be resolved on arXiv — check the log"
        )
    LOG.info("alphaXiv hot feed: %d papers (hot order preserved)", len(items))
    return items
