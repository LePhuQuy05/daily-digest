"""Offline writer-quality evaluation for archived editions.

Usage:
    uv run python tools/writer_eval.py --editions-dir output/editions
    uv run python tools/writer_eval.py --snapshot output/editions/digest-2026-11-21.json
    uv run python tools/writer_eval.py --editions-dir output/editions --baseline output/quality-baseline.json
    uv run python tools/writer_eval.py --editions-dir output/editions --compare output/quality-baseline.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from daily_digest.writer_quality import (
    compare_scores,
    format_score,
    load_snapshot,
    score_payload,
)


def _paths(args: argparse.Namespace) -> list[Path]:
    if args.snapshot:
        return [Path(args.snapshot)]
    if args.editions_dir:
        root = Path(args.editions_dir)
        return sorted(path for path in root.glob("digest-*.json") if path.is_file())
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--snapshot", help="one edition JSON snapshot")
    source.add_argument("--editions-dir", help="directory of digest-*.json snapshots")
    parser.add_argument("--baseline", help="write scores to this JSON file")
    parser.add_argument("--compare", help="compare against this baseline JSON")
    parser.add_argument(
        "--json", action="store_true", help="print JSON instead of text"
    )
    args = parser.parse_args()

    scores: dict[str, dict[str, Any]] = {}
    for path in _paths(args):
        try:
            scores[path.name] = score_payload(load_snapshot(path))
        except (OSError, ValueError, TypeError) as exc:
            print(f"{path}: SKIP {exc}")
            continue
        if not args.json:
            print(f"{path.name}: {format_score(scores[path.name])}")

    if args.json:
        print(json.dumps(scores, ensure_ascii=False, indent=2))

    if args.baseline:
        Path(args.baseline).write_text(
            json.dumps(scores, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"baseline written: {args.baseline}")

    if args.compare:
        baseline = json.loads(Path(args.compare).read_text(encoding="utf-8"))
        for name, score in scores.items():
            if name not in baseline:
                print(f"{name}: no baseline")
                continue
            delta = compare_scores(score, baseline[name])
            print(f"{name}: delta {json.dumps(delta, ensure_ascii=False)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
