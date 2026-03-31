#!/usr/bin/env python3
# ruff: noqa: E402
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

from lib import env, pipeline, render, schema, ui

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
        if normalized not in pipeline.MOCK_AVAILABLE_SOURCES:
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


def emit_output(report: schema.Report, emit: str, quality: dict | None = None) -> str:
    if emit == "json":
        return json.dumps(schema.to_dict(report), indent=2, sort_keys=True)
    if emit in {"compact", "md"}:
        return render.render_compact(report, quality=quality)
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
    parser.add_argument("--x-handle", help="X handle for targeted supplemental search")
    parser.add_argument("--web-backend", default="auto",
                        choices=["auto", "brave", "exa", "serper", "none"],
                        help="Web search backend (default: auto, tries Brave then Exa then Serper)")
    return parser


def _missing_sources_for_promo(diag: dict[str, object]) -> str | None:
    available = set(diag.get("available_sources") or [])
    missing = []
    if "reddit" not in available:
        missing.append("reddit")
    if "x" not in available:
        missing.append("x")
    if "grounding" not in available:
        missing.append("web")
    if not missing:
        return None
    if "reddit" in missing and "x" in missing:
        return "both"
    return missing[0]


def _show_runtime_ui(report: schema.Report, progress: ui.ProgressDisplay, diag: dict[str, object]) -> None:
    counts = {source: len(items) for source, items in report.items_by_source.items()}
    display_sources = list(
        dict.fromkeys(
            [
                *report.query_plan.source_weights.keys(),
                *report.items_by_source.keys(),
                *report.errors_by_source.keys(),
            ]
        )
    )
    progress.end_processing()
    progress.show_complete(
        source_counts=counts,
        display_sources=display_sources,
    )
    promo = _missing_sources_for_promo(diag)
    if promo:
        progress.show_promo(promo, diag=diag)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.debug:
        os.environ["LAST30DAYS_DEBUG"] = "1"

    config = env.get_config()

    # Handle setup subcommand
    topic = " ".join(args.topic).strip()
    if topic.lower() == "setup":
        from lib import setup_wizard
        sys.stderr.write("Running auto-setup...\n")
        results = setup_wizard.run_auto_setup(config)
        from_browser = "auto"
        if results.get("cookies_found"):
            first_browser = next(iter(results["cookies_found"].values()))
            from_browser = first_browser
        setup_wizard.write_setup_config(env.CONFIG_FILE, from_browser=from_browser)
        results["env_written"] = True
        sys.stderr.write(setup_wizard.get_setup_status_text(results) + "\n")
        return 0

    requested_sources = parse_search_flag(args.search) if args.search else None
    diag = pipeline.diagnose(config, requested_sources)

    if args.diagnose:
        print(json.dumps(diag, indent=2, sort_keys=True))
        return 0

    if not topic:
        parser.print_usage(sys.stderr)
        return 2

    ui.show_diagnostic_banner(diag)
    progress = ui.ProgressDisplay(topic, show_banner=True)
    progress.start_processing()

    depth = "deep" if args.deep else "quick" if args.quick else "default"
    try:
        report = pipeline.run(
            topic=topic,
            config=config,
            depth=depth,
            requested_sources=requested_sources,
            mock=args.mock,
            x_handle=args.x_handle,
            web_backend=args.web_backend,
        )
    except Exception as exc:
        progress.end_processing()
        progress.show_error(str(exc))
        raise
    _show_runtime_ui(report, progress, diag)
    if args.store:
        counts = persist_report(report)
        sys.stderr.write(
            f"[last30days] Stored {counts['new']} new, {counts['updated']} updated findings\n"
        )
        sys.stderr.flush()

    # Compute quality score for render output
    quality = None
    try:
        from lib import quality_nudge
        quality = quality_nudge.quality_from_report(config, report)
    except Exception:
        pass

    rendered = emit_output(report, args.emit, quality=quality)
    if args.save_dir:
        save_path = save_output(report, args.emit, args.save_dir)
        sys.stderr.write(f"[last30days] Saved output to {save_path}\n")
        sys.stderr.flush()

    # NUX: signal first-run so SKILL.md can trigger setup wizard
    if args.emit in {"compact", "md"}:
        try:
            from lib import setup_wizard
            if setup_wizard.is_first_run(config):
                print("FIRST_RUN: true")
                print("")
        except Exception:
            pass

    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
