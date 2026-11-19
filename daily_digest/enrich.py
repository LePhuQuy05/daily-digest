"""OpenAlex citation enrichment (api.openalex.org — keyless, ~10 req/s).

One batched request per run: looks up the candidate pool's arXiv papers and
attaches `cited_by_count` to each Item. OpenAlex resolves arXiv DOIs to the
*published* version when one exists, so counts reflect the real paper, not just
the preprint. Verified live 2026-11-19 (docs/paper-sources.md has the probes).

Total function: any failure logs a warning and returns the input unchanged —
citation counts are a nice-to-have, never a delivery dependency.
"""

from __future__ import annotations

import dataclasses
import re

import httpx

from daily_digest.config import Config
from daily_digest.model import Item
from daily_digest.normalize import canonical_arxiv_id, find_arxiv_id
from daily_digest.util import LOG

OPENALEX_WORKS_URL = "https://api.openalex.org/works"
MAX_BATCH = 100  # OpenAlex per-page ceiling for one batched filter request
_ARXIV_DOI = re.compile(r"10\.48550/arxiv\.(\d{4}\.\d{4,6})", re.IGNORECASE)


def _arxiv_doi(arxiv_id: str) -> str:
    return f"https://doi.org/10.48550/arxiv.{arxiv_id}"


def _citations_by_arxiv_id(results: list) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for work in results:
        if not isinstance(work, dict):
            continue
        cited = work.get("cited_by_count")
        if not isinstance(cited, int):
            continue
        arxiv_id: str | None = None
        # 1) direct: the response DOI still matches the constructed arXiv DOI
        ids = work.get("ids") or {}
        doi = ids.get("doi") or ""
        if isinstance(doi, str):
            match = _ARXIV_DOI.search(doi)
            if match:
                arxiv_id = match.group(1)
        # 2) robust: scan locations for an arxiv.org/abs/<id> landing URL
        if arxiv_id is None:
            for location in work.get("locations") or []:
                landing = (
                    location.get("landing_page_url")
                    if isinstance(location, dict)
                    else None
                )
                if isinstance(landing, str):
                    arxiv_id = find_arxiv_id(landing)
                    if arxiv_id:
                        break
        if arxiv_id:
            mapping[arxiv_id] = max(mapping.get(arxiv_id, 0), cited)
    return mapping


def enrich_citations(items: list[Item], config: Config) -> list[Item]:
    """Attach citation counts (OpenAlex) to arXiv-backed items. Never raises."""
    if not config.enrichment.enabled or not items:
        return items

    ids: list[str] = []
    seen: set[str] = set()
    for item in items:
        arxiv_id = canonical_arxiv_id(item.url)
        if arxiv_id and arxiv_id not in seen:
            seen.add(arxiv_id)
            ids.append(arxiv_id)
    if not ids:
        return items
    ids = ids[:MAX_BATCH]

    params = {
        "filter": "doi:" + "|".join(_arxiv_doi(arxiv_id) for arxiv_id in ids),
        "select": "ids,cited_by_count,locations",
        "per-page": str(MAX_BATCH),
    }
    if config.enrichment.email:
        params["mailto"] = config.enrichment.email  # OpenAlex polite pool
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(OPENALEX_WORKS_URL, params=params)
        response.raise_for_status()
        results = response.json().get("results", [])
    except (httpx.HTTPError, ValueError) as exc:
        LOG.warning(
            "OpenAlex enrichment failed (%s: %s); continuing without citations",
            type(exc).__name__,
            exc,
        )
        return items

    citations = _citations_by_arxiv_id(results)
    enriched = 0
    output = []
    for item in items:
        arxiv_id = canonical_arxiv_id(item.url)
        if arxiv_id and arxiv_id in citations:
            item = dataclasses.replace(item, citations=citations[arxiv_id])
            enriched += 1
        output.append(item)
    LOG.info("OpenAlex: citations found for %d/%d arXiv items", enriched, len(ids))
    return output
