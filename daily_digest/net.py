"""Shared network guards: SSRF-safe URL validation and redirect-following GET.

Any fetch of an untrusted article/story URL (HN targets, feed article pages)
goes through here so private hosts and non-global IPs are blocked on every
redirect hop, not just the first URL.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import httpx

MAX_REDIRECTS = 4


def host_is_public(host: str) -> bool:
    """True when every resolved address is a global IP. Separated from
    assert_public_url so tests can monkeypatch DNS resolution."""
    infos = socket.getaddrinfo(host, None)
    return all(ipaddress.ip_address(info[4][0]).is_global for info in infos)


def assert_public_url(url: str) -> None:
    """http(s) only; reject localhost/.local hosts and non-global IPs."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError(f"unsupported URL: {url[:120]}")
    host = parsed.hostname.lower()
    if host in ("localhost", "localhost.localdomain") or host.endswith(".local"):
        raise ValueError(f"private host blocked: {host}")
    if not host_is_public(host):
        raise ValueError(f"private IP blocked: {host}")


def get_public(
    client: httpx.Client,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
    max_redirects: int = MAX_REDIRECTS,
) -> httpx.Response:
    """GET with manual redirects, validating every hop (SSRF-safe)."""
    current = url
    for _ in range(max_redirects):
        assert_public_url(current)
        response = client.get(
            current, headers=headers, timeout=timeout, follow_redirects=False
        )
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("location")
            if not location:
                response.raise_for_status()
            current = urljoin(current, location)
            continue
        response.raise_for_status()
        return response
    raise httpx.TooManyRedirects(f"too many redirects: {url[:120]}")
