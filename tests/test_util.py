"""Regression tests for util plumbing."""

import io

import pytest

from daily_digest.util import _force_utf8


def test_force_utf8_rescues_legacy_codepage_streams(tmp_path):
    """A cp932-style console stream must not crash on non-ASCII after _force_utf8."""
    raw = (tmp_path / "console.txt").open("wb")
    stream = io.TextIOWrapper(raw, encoding="cp932")

    with pytest.raises(UnicodeEncodeError):
        stream.write("toast — click it\n")
        stream.flush()

    _force_utf8(stream)
    stream.write("toast — click it\n")  # must not raise anymore
    stream.flush()
    stream.close()

    content = (tmp_path / "console.txt").read_text(encoding="utf-8")
    assert "toast — click it" in content


def test_force_utf8_tolerates_non_reconfigurable_streams():
    import io as _io

    stream = _io.StringIO()  # no .reconfigure — must be a no-op, not a crash
    _force_utf8(stream)
    stream.write("fine")
    assert stream.getvalue() == "fine"
