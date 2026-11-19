"""Best-effort article images: real arXiv figures + article OG only.

Design:
- Only hero + section-lead items are considered (no tiny brief thumbnails).
- arXiv: first `ltx_figure` from `arxiv.org/html/<id>`; `<img>` is downloaded,
  inline `<svg>` is rasterized via headless Edge (figcaption hidden, auto-trim).
- HN: story target via Algolia, then its OG image.
- Generic article: OG/Twitter image; reject logos, HF page-1 cards, auto GitHub
  banners. No LLM-generated images.
- Every image is reviewed by the app LLM (vision) when available; failures and
  timeouts never block the digest.
"""

from __future__ import annotations

import base64
import hashlib
import io
import ipaddress
import json
import re
import shutil
import socket
import subprocess
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from PIL import Image, ImageChops

from daily_digest.config import Config
from daily_digest.frontpage import build_front_page
from daily_digest.model import RankedItem
from daily_digest.util import LOG, PROJECT_ROOT

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)
REJECT_URL_PARTS = (
    "arxiv-logo",
    "social-thumbnails/papers",
    "opengraph.githubassets.com",
    "favicon",
    "/icons/",
    "icon-",
)
MAX_FIGURES = 2


@dataclass(frozen=True)
class ImageAsset:
    uid: str
    data_uri: str
    alt: str
    credit: str
    source_url: str
    kind: str
    width: int
    height: int


@dataclass(frozen=True)
class Candidate:
    kind: str
    source_url: str
    alt: str
    credit: str
    image_urls: tuple[str, ...] = ()
    svg_html: str = ""
    styles: str = ""
    base_url: str = ""
    svg_url: str = ""


def _clean_text(value: str, limit: int = 220) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _og_from_html(html: str, base_url: str, title: str) -> list[Candidate]:
    url = ""
    for pattern in (
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)',
    ):
        match = re.search(pattern, html, re.I)
        if match:
            url = match.group(1)
            break
    if not url:
        return []
    url = urljoin(base_url, url)
    low = url.lower()
    if low.startswith("data:") or any(part in low for part in REJECT_URL_PARTS):
        return []
    host = urlparse(url).netloc
    return [
        Candidate(
            kind="og",
            source_url=url,
            alt=_clean_text(title),
            credit=f"Ảnh: {host}",
            image_urls=(url,),
        )
    ]


def _arxiv_candidates(
    html: str, final_url: str, title: str, arxiv_id: str
) -> list[Candidate]:
    styles = "\n".join(re.findall(r"<style[^>]*>.*?</style>", html, re.S | re.I)[:8])[
        :200_000
    ]
    figures = re.findall(
        r'<figure\b[^>]*class="[^"]*ltx_figure[^"]*"[^>]*>.*?</figure>',
        html,
        re.S | re.I,
    )
    candidates: list[Candidate] = []
    for figure in figures:
        if re.search(r'class="[^"]*ltx_table', figure, re.I):
            continue
        caption = ""
        cap_match = re.search(
            r"<figcaption[^>]*>(.*?)</figcaption>", figure, re.S | re.I
        )
        if cap_match:
            caption = _clean_text(cap_match.group(1))
        alt = caption or title
        credit = f"Hình: arXiv:{arxiv_id}"
        img = re.search(r'<img[^>]+src=["\']([^"\']+)', figure, re.I)
        src = img.group(1) if img else ""
        if (
            src
            and not src.startswith("data:")
            and not any(part in src.lower() for part in ("logo", "icon", "spacer"))
        ):
            urls: list[str] = []
            if src.startswith("http"):
                urls = [src]
            else:
                for base in ("https://arxiv.org/html/", final_url + "/", final_url):
                    resolved = urljoin(base, src)
                    if resolved not in urls:
                        urls.append(resolved)
            if urls:
                candidates.append(
                    Candidate(
                        kind="arxiv_img",
                        source_url=final_url,
                        alt=alt,
                        credit=credit,
                        image_urls=tuple(urls[:3]),
                    )
                )
        elif "<svg" in figure.lower():
            candidates.append(
                Candidate(
                    kind="arxiv_svg",
                    source_url=final_url,
                    alt=alt,
                    credit=credit,
                    svg_html=figure,
                    styles=styles,
                    base_url=f"https://arxiv.org/html/{arxiv_id}",
                )
            )
        else:
            obj = re.search(r'<object[^>]+data=["\']([^"\']+)', figure, re.I)
            if obj:
                candidates.append(
                    Candidate(
                        kind="arxiv_svg",
                        source_url=final_url,
                        alt=alt,
                        credit=credit,
                        svg_html=figure,
                        styles=styles,
                        base_url="https://arxiv.org/html/",
                        svg_url=urljoin("https://arxiv.org/html/", obj.group(1)),
                    )
                )
        if len(candidates) >= MAX_FIGURES:
            break
    return candidates


def _hn_target(client: httpx.Client, url: str) -> str:
    match = re.search(r"id=(\d+)", url)
    if not match:
        return ""
    try:
        data = _get_json(
            client, f"https://hn.algolia.com/api/v1/items/{match.group(1)}"
        )
    except Exception:
        return ""
    target = data.get("url") or ""
    if not target:
        text = data.get("text") or ""
        link = re.search(r'href=["\'](https?://[^"\']+)', text, re.I)
        target = link.group(1) if link else ""
    return target


def _assert_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError(f"unsupported image URL: {url[:120]}")
    host = parsed.hostname.lower()
    if host in ("localhost", "localhost.localdomain") or host.endswith(".local"):
        raise ValueError("private image host blocked")
    infos = socket.getaddrinfo(host, None)
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise ValueError(f"private image IP blocked: {ip}")


def _get(client: httpx.Client, url: str) -> httpx.Response:
    current = url
    for _ in range(4):
        _assert_public_url(current)
        response = client.get(current, follow_redirects=False)
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("location")
            if not location:
                response.raise_for_status()
            current = urljoin(current, location)
            continue
        response.raise_for_status()
        return response
    raise httpx.TooManyRedirects("too many image redirects")


def _get_text(client: httpx.Client, url: str, limit: int = 4_000_000) -> str:
    response = _get(client, url)
    return response.text[:limit]


def _get_json(client: httpx.Client, url: str) -> dict:
    response = _get(client, url)
    return response.json()


def _candidates_for(
    item: RankedItem, client: httpx.Client, config: Config
) -> list[Candidate]:
    url = item.item.url
    if "arxiv.org/abs/" in url or "arxiv.org/pdf/" in url:
        arxiv_id = re.split(r"/(?:abs|pdf)/", url, maxsplit=1)[1].split("?")[0]
        try:
            final_url = f"https://arxiv.org/html/{arxiv_id}"
            html = _get_text(client, final_url)
        except Exception as exc:  # noqa: BLE001
            LOG.info("media: arXiv HTML unavailable for %s (%s)", arxiv_id, exc)
            return []
        return _arxiv_candidates(html, final_url, item.item.title, arxiv_id)

    if "news.ycombinator.com/item" in url:
        target = _hn_target(client, url)
        if not target:
            return []
        url = target

    if "github.com/" in url and "opengraph.githubassets.com" in url:
        return []
    try:
        html = _get_text(client, url)
    except Exception as exc:  # noqa: BLE001
        LOG.info("media: article HTML unavailable for %s (%s)", url, exc)
        return []
    return _og_from_html(html, url, item.item.title)


def _find_edge() -> Path | None:
    candidates = (
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    )
    for path in candidates:
        if path.exists():
            return path
    found = shutil.which("msedge")
    return Path(found) if found else None


def _sanitize_fragment(value: str) -> str:
    value = re.sub(r"<script\b.*?</script>", "", value, flags=re.S | re.I)
    value = re.sub(r"<iframe\b.*?</iframe>", "", value, flags=re.S | re.I)
    value = re.sub(r"<(object|embed|link)\b[^>]*>", "", value, flags=re.I)
    value = re.sub(r"\son\w+\s*=\s*([\"']).*?\1", "", value, flags=re.I | re.S)
    value = re.sub(r"javascript:", "", value, flags=re.I)
    return value


def _rasterize_svg(
    candidate: Candidate, width: int, client: httpx.Client | None = None
) -> tuple[bytes, int, int] | None:
    edge = _find_edge()
    if not edge:
        return None
    figure = candidate.svg_html
    if candidate.svg_url:
        if client is None:
            return None
        try:
            response = _get(client, candidate.svg_url)
            svg = _sanitize_fragment(response.text)
        except Exception as exc:  # noqa: BLE001
            LOG.info("media: SVG download failed (%s)", exc)
            return None
        if "<svg" not in svg.lower():
            return None
        figure = re.sub(r"<object\b.*?</object>", svg, figure, flags=re.S | re.I)
    figure = _sanitize_fragment(figure)
    styles = _sanitize_fragment(candidate.styles)
    wrapper = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<base href='{candidate.base_url}'>"
        f"{styles}"
        "<style>html,body{margin:0;padding:0;background:#fff;}"
        f"body{{width:{width}px;}}.ltx_figure{{width:{width}px;margin:0!important;"
        "padding:0!important;}figcaption,.ltx_caption{display:none!important;}"
        "svg{width:100%!important;max-width:100%!important;height:auto!important;}"
        "object,img{width:100%!important;max-width:100%!important;height:auto!important;}"
        "</style></head><body>" + figure + "</body></html>"
    )
    with tempfile.TemporaryDirectory(prefix="digest-fig-") as tmp:
        tmp_path = Path(tmp)
        page = tmp_path / "figure.html"
        shot = tmp_path / "figure.png"
        profile = tmp_path / "edge-profile"
        page.write_text(wrapper, encoding="utf-8")
        try:
            subprocess.run(
                [
                    str(edge),
                    "--headless=new",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-gpu",
                    "--hide-scrollbars",
                    f"--user-data-dir={profile}",
                    "--virtual-time-budget=2000",
                    f"--window-size={width + 200},2600",
                    f"--screenshot={shot}",
                    page.as_uri(),
                ],
                capture_output=True,
                timeout=45,
            )
            if not shot.exists():
                return None
            img = Image.open(shot).convert("RGB")
            diff = ImageChops.difference(
                img, Image.new("RGB", img.size, (255, 255, 255))
            ).convert("L")
            bbox = diff.point(lambda p: 255 if p > 8 else 0).getbbox()
            if bbox:
                img = img.crop(bbox)
            if img.width < 240 or img.height < 120:
                return None
            img.thumbnail((width, width * 2))
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=88)
            return buf.getvalue(), img.width, img.height
        except Exception as exc:  # noqa: BLE001
            LOG.info("media: SVG rasterization failed (%s)", exc)
            return None


def _download_image(
    client: httpx.Client, candidate: Candidate, width: int, max_bytes: int
) -> tuple[bytes, int, int] | None:
    for url in candidate.image_urls:
        try:
            response = _get(client, url)
            content_type = response.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                continue
            if len(response.content) > max_bytes:
                continue
            img = Image.open(io.BytesIO(response.content))
            img.verify()
            img = Image.open(io.BytesIO(response.content)).convert("RGB")
            img.thumbnail((width, width * 2))
            if img.width < 240 or img.height < 120:
                continue
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=88)
            return buf.getvalue(), img.width, img.height
        except Exception as exc:  # noqa: BLE001
            LOG.info("media: image fetch failed (%s) %s", exc, url[:100])
    return None


def _review_image(
    chat: Callable[[list[dict]], str] | None,
    image_bytes: bytes,
    title: str,
    caption: str,
) -> bool:
    if chat is None:
        return True
    b64 = base64.b64encode(image_bytes).decode("ascii")
    prompt = (
        "You are the visual editor of a technical AI news digest. "
        f"Article title: {title!r}. Figure caption: {caption!r}. "
        "Look at this image candidate. Is it a genuine, legible figure, diagram "
        "or photo that helps a reader, or is it a logo, table, text screenshot, "
        "or placeholder? Reply with JSON only: "
        '{"suitable": true|false, "kind": "figure|chart|diagram|photo|logo|table|text|other", '
        '"reason": "short"}'
    )
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                },
            ],
        }
    ]
    try:
        raw = chat(messages)
    except Exception as exc:  # noqa: BLE001
        LOG.info("media: LLM review failed (%s); accepting candidate", exc)
        return True
    match = re.search(r"\{.*\}", raw or "", re.S)
    if not match:
        return True
    try:
        verdict = json.loads(match.group(0))
    except json.JSONDecodeError:
        return True
    if verdict.get("suitable") is False:
        LOG.info("media: LLM rejected image: %s", verdict.get("reason", ""))
        return False
    return True


def _cache_path(candidate: Candidate, config: Config) -> Path:
    raw = (
        candidate.kind + "|" + candidate.source_url + "|" + candidate.image_urls[0]
        if candidate.image_urls
        else candidate.kind + "|" + candidate.source_url + "|" + candidate.svg_html
    )
    key = hashlib.sha1(raw.encode("utf-8", errors="replace")).hexdigest()[:16]
    root = Path(config.media.cache_dir)
    if not root.is_absolute():
        root = PROJECT_ROOT / root
    return root / f"{key}.jpg"


def _prepare_candidate(
    candidate: Candidate,
    client: httpx.Client,
    config: Config,
    chat: Callable[[list[dict]], str] | None,
    title: str,
) -> ImageAsset | None:
    cache = _cache_path(candidate, config)
    cache.parent.mkdir(parents=True, exist_ok=True)
    if cache.exists():
        data = cache.read_bytes()
        img = Image.open(io.BytesIO(data))
        width, height = img.width, img.height
    else:
        prepared = (
            _rasterize_svg(candidate, config.media.width, client)
            if candidate.svg_html
            else _download_image(
                client, candidate, config.media.width, config.media.max_bytes
            )
        )
        if not prepared:
            return None
        data, width, height = prepared
        try:
            cache.write_bytes(data)
        except OSError:
            pass
    if config.media.llm_review and not _review_image(chat, data, title, candidate.alt):
        return None
    return ImageAsset(
        uid="",
        data_uri="data:image/jpeg;base64," + base64.b64encode(data).decode("ascii"),
        alt=candidate.alt,
        credit=candidate.credit,
        source_url=candidate.source_url,
        kind=candidate.kind,
        width=width,
        height=height,
    )


def collect_images(
    ranked: Sequence[RankedItem],
    config: Config,
    chat: Callable[[list[dict]], str] | None = None,
) -> dict[str, ImageAsset]:
    """Best-effort images for hero + section leads; returns {} on any failure."""
    if not config.media.enabled or not ranked:
        return {}
    page = build_front_page(ranked)
    targets = []
    if page.lead:
        targets.append(page.lead)
    for section in page.sections:
        if section.lead:
            targets.append(section.lead)
    seen: set[str] = set()
    assets: dict[str, ImageAsset] = {}
    used_bytes = 0
    with httpx.Client(
        timeout=config.media.timeout_seconds,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=False,
    ) as client:
        for item in targets[: config.media.max_images]:
            uid = item.item.id
            if uid in seen:
                continue
            seen.add(uid)
            try:
                candidates = _candidates_for(item, client, config)
            except Exception as exc:  # noqa: BLE001
                LOG.info("media: no candidates for %s (%s)", uid, exc)
                continue
            for candidate in candidates:
                try:
                    asset = _prepare_candidate(
                        candidate, client, config, chat, item.item.title
                    )
                except Exception as exc:  # noqa: BLE001
                    LOG.info("media: candidate failed for %s (%s)", uid, exc)
                    continue
                if not asset:
                    continue
                if used_bytes + len(asset.data_uri) > config.media.max_total_bytes:
                    LOG.info("media: total image budget reached at %s", uid)
                    break
                used_bytes += len(asset.data_uri)
                assets[uid] = ImageAsset(
                    uid=uid,
                    data_uri=asset.data_uri,
                    alt=asset.alt,
                    credit=asset.credit,
                    source_url=asset.source_url,
                    kind=asset.kind,
                    width=asset.width,
                    height=asset.height,
                )
                LOG.info(
                    "media: image for %s (%s, %d bytes)",
                    uid,
                    asset.kind,
                    len(asset.data_uri),
                )
                break
    LOG.info("media: %d/%d target slots filled", len(assets), len(targets))
    return assets
