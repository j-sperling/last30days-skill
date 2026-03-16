#!/usr/bin/env python3
"""last30days v3.0.0 CLI."""

from __future__ import annotations

import argparse
import atexit
import json
import os
import re
import signal
import sys
import threading
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

from lib import env, pipeline, render, schema

_child_pids: set[int] = set()
_child_pids_lock = threading.Lock()


def register_child_pid(pid: int) -> None:
    with _child_pids_lock:
        _child_pids.add(pid)


def unregister_child_pid(pid: int) -> None:
    with _child_pids_lock:
        _child_pids.discard(pid)


def _cleanup_children() -> None:
    with _child_pids_lock:
        pids = list(_child_pids)
    for pid in pids:
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            continue


atexit.register(_cleanup_children)


def parse_search_flag(raw: str) -> list[str]:
    sources = []
    for source in raw.split(","):
        source = source.strip().lower()
        if not source:
            continue
        normalized = pipeline.SEARCH_ALIAS.get(source, source)
        if normalized not in {
            "reddit",
            "x",
            "youtube",
            "tiktok",
            "instagram",
            "hackernews",
            "bluesky",
            "truthsocial",
            "polymarket",
            "grounding",
            "xiaohongshu",
        }:
            raise SystemExit(f"Unknown search source: {source}")
        if normalized not in sources:
            sources.append(normalized)
    if not sources:
        raise SystemExit("--search requires at least one source.")
    return sources


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "last30days"


def save_output(report: schema.Report, emit: str, save_dir: str) -> Path:
    path = Path(save_dir).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    extension = "json" if emit == "json" else "md"
    out_path = path / f"{slugify(report.topic)}.{extension}"
    content = emit_output(report, emit)
    out_path.write_text(content)
    return out_path


def emit_output(report: schema.Report, emit: str) -> str:
    if emit == "json":
        return json.dumps(schema.to_dict(report), indent=2, sort_keys=True)
    if emit in {"compact", "md"}:
        return render.render_compact(report)
    if emit == "context":
        return render.render_context(report)
    raise SystemExit(f"Unsupported emit mode: {emit}")


def persist_report(report: schema.Report) -> dict[str, int]:
    import store

    store.init_db()
    topic_row = store.add_topic(report.topic)
    topic_id = topic_row["id"]
    source_mode = ",".join(sorted(report.items_by_source)) or "v3"
    run_id = store.record_run(topic_id, source_mode=source_mode, status="running")
    try:
        findings = store.findings_from_report(report)
        counts = store.store_findings(run_id, topic_id, findings)
        store.update_run(
            run_id,
            status="completed",
            findings_new=counts["new"],
            findings_updated=counts["updated"],
        )
        return counts
    except Exception as exc:
        store.update_run(run_id, status="failed", error_message=str(exc)[:500])
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Research a topic across live social, market, and grounded web sources.")
    parser.add_argument("topic", nargs="*", help="Research topic")
    parser.add_argument("--emit", default="compact", choices=["compact", "json", "context", "md"])
    parser.add_argument("--search", help="Comma-separated source list")
    parser.add_argument("--quick", action="store_true", help="Lower-latency retrieval profile")
    parser.add_argument("--deep", action="store_true", help="Higher-recall retrieval profile")
    parser.add_argument("--debug", action="store_true", help="Enable HTTP debug logging")
    parser.add_argument("--mock", action="store_true", help="Use mock retrieval fixtures")
    parser.add_argument("--diagnose", action="store_true", help="Print provider and source availability")
    parser.add_argument("--save-dir", help="Optional directory for saving the rendered output")
    parser.add_argument("--store", action="store_true", help="Persist ranked findings to the SQLite research store")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.debug:
        os.environ["LAST30DAYS_DEBUG"] = "1"

    config = env.get_config()
    requested_sources = parse_search_flag(args.search) if args.search else None

    if args.diagnose:
        print(json.dumps(pipeline.diagnose(config, requested_sources), indent=2, sort_keys=True))
        return 0

    topic = " ".join(args.topic).strip()
    if not topic:
        parser.print_usage(sys.stderr)
        return 2

    depth = "deep" if args.deep else "quick" if args.quick else "default"
    report = pipeline.run(
        topic=topic,
        config=config,
        depth=depth,
        requested_sources=requested_sources,
        mock=args.mock,
    )
    if args.store:
        counts = persist_report(report)
        sys.stderr.write(
            f"[last30days] Stored {counts['new']} new, {counts['updated']} updated findings\n"
        )
        sys.stderr.flush()

    rendered = emit_output(report, args.emit)
    if args.save_dir:
        save_path = save_output(report, args.emit, args.save_dir)
        sys.stderr.write(f"[last30days] Saved output to {save_path}\n")
        sys.stderr.flush()
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
