from daily_digest.model import Item
from daily_digest.normalize import (
    canonical_arxiv_id,
    find_arxiv_id,
    item_uid,
    normalize_url,
    safe_href,
)
from helpers import make_item


def test_canonical_arxiv_id_matrix():
    assert canonical_arxiv_id("https://arxiv.org/abs/2611.21622") == "2611.21622"
    assert canonical_arxiv_id("http://arxiv.org/pdf/2407.21583v2") == "2407.21583"
    assert canonical_arxiv_id("https://www.arxiv.org/abs/2407.21583v1/") == "2407.21583"
    assert (
        canonical_arxiv_id("https://huggingface.co/papers/2611.21938") == "2611.21938"
    )
    assert (
        canonical_arxiv_id("https://export.arxiv.org/abs/cs/0112017v1") == "cs/0112017"
    )
    assert canonical_arxiv_id("https://example.com/not-arxiv") is None


def test_normalize_url_strips_utm_and_normalizes():
    assert (
        normalize_url("https://Example.com/path/?utm_source=x&id=7")
        == "https://example.com/path?id=7"
    )
    assert normalize_url("https://example.com/path/") == "https://example.com/path"
    assert normalize_url("https://example.com") == "https://example.com/"


def test_safe_href_blocks_non_http():
    assert safe_href("javascript:alert(1)") == "#"
    assert safe_href("data:text/html,evil") == "#"
    assert safe_href("https://example.com") == "https://example.com"
    assert safe_href("http://example.com") == "http://example.com"


def test_item_uid_prefers_arxiv_id():
    arxiv = make_item(
        id="arxiv:2611.12345",
        title="t",
        url="https://arxiv.org/abs/2611.12345v2",
        source="arxiv",
    )
    hf = make_item(
        id="arxiv:2611.12345",
        title="t",
        url="https://huggingface.co/papers/2611.12345",
        source="hf_papers",
    )
    hn = make_item(id="hn:42", title="t", url="https://example.com/x", source="hn")
    other = Item(id="x", title="t", url="https://example.com/y", source="other")
    assert item_uid(arxiv) == "arxiv:2611.12345"
    assert item_uid(hf) == "arxiv:2611.12345"  # same paper, same uid -> merged
    assert item_uid(hn) == "hn:42"
    assert item_uid(other).startswith("url:")


def test_find_arxiv_id_in_free_text():
    blob = '<p>Abstract:</p><p>We study LLMs.</p><p>arXiv: <a href="https://arxiv.org/abs/2611.14996">https://arxiv.org/abs/2611.14996</a></p>'
    assert find_arxiv_id(blob) == "2611.14996"
    assert find_arxiv_id("see https://arxiv.org/abs/2407.21583v2 for details") == "2407.21583"
    assert find_arxiv_id("no paper link in here at all") is None
