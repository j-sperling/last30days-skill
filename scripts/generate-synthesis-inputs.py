#!/usr/bin/env python3
"""Convert saved v3 JSON reports into compact markdown renderings."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from lib import render, schema

JSON_DIR = Path(__file__).parent.parent / "docs" / "comparison-results" / "json"
COMPACT_DIR = Path(__file__).parent.parent / "docs" / "comparison-results" / "compact"


def main() -> int:
    COMPACT_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(path for path in JSON_DIR.glob("*.json") if path.name != "diagnose-baseline.json")
    print(f"Converting {len(files)} JSON files to compact markdown...\n")
    for json_file in files:
        payload = json.loads(json_file.read_text())
        report = schema.report_from_dict(payload)
        compact = render.render_compact(report)
        out_path = COMPACT_DIR / json_file.with_suffix(".md").name
        out_path.write_text(compact)
        print(
            f"  {json_file.name:40s} -> {len(compact):5d} chars "
            f"(clusters:{len(report.clusters)} candidates:{len(report.ranked_candidates)} sources:{len(report.items_by_source)})"
        )
    print(f"\nDone. {len(files)} compact files written to {COMPACT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
