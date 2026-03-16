"""Cluster-first rendering for the v3 pipeline."""

from __future__ import annotations

from . import schema


def render_compact(report: schema.Report, cluster_limit: int = 8) -> str:
    lines = [
        f"# last30days v3.0.0: {report.topic}",
        "",
        f"- Date range: {report.range_from} to {report.range_to}",
        f"- Intent: {report.query_plan.intent}",
        f"- Planner: {report.provider_runtime.reasoning_provider} / {report.provider_runtime.planner_model}",
        f"- Reranker: {report.provider_runtime.rerank_model}",
        "",
    ]

    if report.warnings:
        lines.append("## Warnings")
        lines.extend(f"- {warning}" for warning in report.warnings)
        lines.append("")

    lines.append("## Ranked Evidence Clusters")
    lines.append("")
    candidate_by_id = {candidate.candidate_id: candidate for candidate in report.ranked_candidates}
    for index, cluster in enumerate(report.clusters[:cluster_limit], start=1):
        lines.append(
            f"### {index}. {cluster.title} "
            f"(score {cluster.score:.1f}, {len(cluster.candidate_ids)} item{'s' if len(cluster.candidate_ids) != 1 else ''}, "
            f"sources: {', '.join(cluster.sources)})"
        )
        if cluster.uncertainty:
            lines.append(f"- Uncertainty: {cluster.uncertainty}")
        for rep_index, candidate_id in enumerate(cluster.representative_ids, start=1):
            candidate = candidate_by_id.get(candidate_id)
            if not candidate:
                continue
            lines.extend(_render_candidate(candidate, prefix=f"{rep_index}."))
        lines.append("")

    lines.append("## Source Coverage")
    lines.append("")
    for source, items in sorted(report.items_by_source.items()):
        lines.append(f"- {source}: {len(items)} item{'s' if len(items) != 1 else ''}")

    if report.errors_by_source:
        lines.append("")
        lines.append("## Source Errors")
        lines.append("")
        for source, error in sorted(report.errors_by_source.items()):
            lines.append(f"- {source}: {error}")

    return "\n".join(lines).strip() + "\n"


def render_context(report: schema.Report, cluster_limit: int = 6) -> str:
    candidate_by_id = {candidate.candidate_id: candidate for candidate in report.ranked_candidates}
    lines = [
        f"Topic: {report.topic}",
        f"Intent: {report.query_plan.intent}",
        "Top clusters:",
    ]
    for cluster in report.clusters[:cluster_limit]:
        lines.append(f"- {cluster.title} [{', '.join(cluster.sources)}]")
        for candidate_id in cluster.representative_ids[:2]:
            candidate = candidate_by_id.get(candidate_id)
            if not candidate:
                continue
            lines.append(
                f"  - {candidate.source}: {candidate.title} | {candidate.url} | {candidate.snippet[:180]}"
            )
    if report.warnings:
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in report.warnings)
    return "\n".join(lines).strip() + "\n"


def _render_candidate(candidate: schema.Candidate, prefix: str) -> list[str]:
    lines = [
        f"{prefix} [{candidate.source}] {candidate.title}",
        f"   - URL: {candidate.url}",
        f"   - Score: {candidate.final_score:.1f} | rerank={candidate.rerank_score or 0:.1f} | rrf={candidate.rrf_score:.4f}",
    ]
    if candidate.explanation:
        lines.append(f"   - Why: {candidate.explanation}")
    if candidate.snippet:
        lines.append(f"   - Evidence: {candidate.snippet[:360]}")
    return lines
