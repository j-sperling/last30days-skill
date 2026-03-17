"""Cluster-first rendering for the v3 pipeline."""

from __future__ import annotations

from . import dates, schema

SOURCE_LABELS = {
    "grounding": "Grounded Web",
    "hackernews": "Hacker News",
    "truthsocial": "Truth Social",
    "xiaohongshu": "Xiaohongshu",
    "x": "X",
}


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

    freshness_warning = _assess_data_freshness(report)
    if freshness_warning:
        lines.extend([
            "## Freshness",
            f"- {freshness_warning}",
            "",
        ])

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
            f"(score {cluster.score:.0f}, {len(cluster.candidate_ids)} item{'s' if len(cluster.candidate_ids) != 1 else ''}, "
            f"sources: {', '.join(_source_label(source) for source in cluster.sources)})"
        )
        if cluster.uncertainty:
            lines.append(f"- Uncertainty: {cluster.uncertainty}")
        for rep_index, candidate_id in enumerate(cluster.representative_ids, start=1):
            candidate = candidate_by_id.get(candidate_id)
            if not candidate:
                continue
            lines.extend(_render_candidate(candidate, prefix=f"{rep_index}."))
        lines.append("")

    lines.extend(_render_source_coverage(report))
    return "\n".join(lines).strip() + "\n"


def render_context(report: schema.Report, cluster_limit: int = 6) -> str:
    candidate_by_id = {candidate.candidate_id: candidate for candidate in report.ranked_candidates}
    lines = [
        f"Topic: {report.topic}",
        f"Intent: {report.query_plan.intent}",
    ]
    freshness_warning = _assess_data_freshness(report)
    if freshness_warning:
        lines.append(f"Freshness warning: {freshness_warning}")
    lines.append("Top clusters:")
    for cluster in report.clusters[:cluster_limit]:
        lines.append(f"- {cluster.title} [{', '.join(_source_label(source) for source in cluster.sources)}]")
        for candidate_id in cluster.representative_ids[:2]:
            candidate = candidate_by_id.get(candidate_id)
            if not candidate:
                continue
            detail_parts = [
                schema.candidate_source_label(candidate),
                candidate.title,
                schema.candidate_best_published_at(candidate) or "date unknown",
                candidate.url,
            ]
            lines.append(f"  - {' | '.join(detail_parts)}")
            if candidate.snippet:
                lines.append(f"    Evidence: {_truncate(candidate.snippet, 180)}")
    if report.warnings:
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in report.warnings)
    return "\n".join(lines).strip() + "\n"


def _render_candidate(candidate: schema.Candidate, prefix: str) -> list[str]:
    primary = schema.candidate_primary_item(candidate)
    detail_parts = [
        _format_date(primary),
        _format_actor(primary),
        _format_engagement(primary),
        f"score:{candidate.final_score:.0f}",
    ]
    details = " | ".join(part for part in detail_parts if part)
    lines = [
        f"{prefix} [{schema.candidate_source_label(candidate)}] {candidate.title}",
        f"   - {details}",
        f"   - URL: {candidate.url}",
    ]
    corroboration = _format_corroboration(candidate)
    if corroboration:
        lines.append(f"   - {corroboration}")
    explanation = _format_explanation(candidate)
    if explanation:
        lines.append(f"   - Why: {explanation}")
    if candidate.snippet:
        lines.append(f"   - Evidence: {_truncate(candidate.snippet, 360)}")
    top_comment = _top_comment_excerpt(primary)
    if top_comment:
        lines.append(f"   - Top comment: {_truncate(top_comment, 240)}")
    insight = _comment_insight(primary)
    if insight:
        lines.append(f"   - Insight: {_truncate(insight, 220)}")
    return lines


def _render_source_coverage(report: schema.Report) -> list[str]:
    lines = [
        "## Source Coverage",
        "",
    ]
    for source, items in sorted(report.items_by_source.items()):
        lines.append(f"- {_source_label(source)}: {len(items)} item{'s' if len(items) != 1 else ''}")
    if report.errors_by_source:
        lines.append("")
        lines.append("## Source Errors")
        lines.append("")
        for source, error in sorted(report.errors_by_source.items()):
            lines.append(f"- {_source_label(source)}: {error}")
    return lines


def _assess_data_freshness(report: schema.Report) -> str | None:
    dated_items = [
        item
        for items in report.items_by_source.values()
        for item in items
        if item.published_at
    ]
    if not dated_items:
        return "Limited recent data: no usable dated evidence made it into the retrieved pool."
    recent_items = [
        item
        for item in dated_items
        if (dates.days_ago(item.published_at) or 10**9) <= 7
    ]
    if len(recent_items) < 3:
        return f"Limited recent data: only {len(recent_items)} of {len(dated_items)} dated items are from the last 7 days."
    if len(recent_items) * 2 < len(dated_items):
        return f"Recent evidence is thin: only {len(recent_items)} of {len(dated_items)} dated items are from the last 7 days."
    return None


def _format_date(item: schema.SourceItem | None) -> str:
    if not item or not item.published_at:
        return "date unknown [date:low]"
    if item.date_confidence == "high":
        return item.published_at
    return f"{item.published_at} [date:{item.date_confidence}]"


def _format_actor(item: schema.SourceItem | None) -> str | None:
    if not item:
        return None
    if item.source == "reddit" and item.container:
        return f"r/{item.container}"
    if item.source in {"x", "bluesky", "truthsocial"} and item.author:
        return f"@{item.author.lstrip('@')}"
    if item.source == "youtube" and item.author:
        return item.author
    if item.container and item.container != "Polymarket":
        return item.container
    if item.author:
        return item.author
    return None


def _format_engagement(item: schema.SourceItem | None) -> str | None:
    if not item or not item.engagement:
        return None
    engagement = item.engagement
    formatters = {
        "reddit": lambda: _fmt_pairs(
            [
                (engagement.get("score"), "pts"),
                (engagement.get("num_comments"), "cmt"),
            ]
        ),
        "x": lambda: _fmt_pairs(
            [
                (engagement.get("likes"), "likes"),
                (engagement.get("reposts"), "rt"),
                (engagement.get("replies"), "re"),
            ]
        ),
        "youtube": lambda: _fmt_pairs(
            [
                (engagement.get("views"), "views"),
                (engagement.get("likes"), "likes"),
                (engagement.get("comments"), "cmt"),
            ]
        ),
        "tiktok": lambda: _fmt_pairs(
            [
                (engagement.get("views"), "views"),
                (engagement.get("likes"), "likes"),
                (engagement.get("comments"), "cmt"),
            ]
        ),
        "instagram": lambda: _fmt_pairs(
            [
                (engagement.get("views"), "views"),
                (engagement.get("likes"), "likes"),
                (engagement.get("comments"), "cmt"),
            ]
        ),
        "hackernews": lambda: _fmt_pairs(
            [
                (engagement.get("points"), "pts"),
                (engagement.get("comments"), "cmt"),
            ]
        ),
        "bluesky": lambda: _fmt_pairs(
            [
                (engagement.get("likes"), "likes"),
                (engagement.get("reposts"), "rt"),
                (engagement.get("replies"), "re"),
            ]
        ),
        "truthsocial": lambda: _fmt_pairs(
            [
                (engagement.get("likes"), "likes"),
                (engagement.get("reposts"), "rt"),
                (engagement.get("replies"), "re"),
            ]
        ),
        "polymarket": lambda: _fmt_pairs(
            [
                (engagement.get("volume"), "vol"),
                (engagement.get("liquidity"), "liq"),
            ]
        ),
    }
    text = formatters.get(item.source, lambda: _fmt_pairs(list(engagement.items())[:3]))()
    return f"[{text}]" if text else None


def _fmt_pairs(pairs: list[tuple[object, str]]) -> str:
    rendered = []
    for value, suffix in pairs:
        if value in (None, "", 0, 0.0):
            continue
        rendered.append(f"{_format_number(value)}{suffix}")
    return ", ".join(rendered)


def _format_number(value: object) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)
    if numeric >= 1000 and numeric.is_integer():
        return f"{int(numeric):,}"
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:.1f}"


def _format_corroboration(candidate: schema.Candidate) -> str | None:
    corroborating = [
        _source_label(source)
        for source in schema.candidate_sources(candidate)
        if source != candidate.source
    ]
    if not corroborating:
        return None
    return f"Also on: {', '.join(corroborating)}"


def _format_explanation(candidate: schema.Candidate) -> str | None:
    if not candidate.explanation or candidate.explanation == "fallback-local-score":
        return None
    return candidate.explanation


def _top_comment_excerpt(item: schema.SourceItem | None) -> str | None:
    if not item:
        return None
    comments = item.metadata.get("top_comments") or []
    if not comments or not isinstance(comments[0], dict):
        return None
    top = comments[0]
    return str(top.get("excerpt") or top.get("text") or "").strip() or None


def _comment_insight(item: schema.SourceItem | None) -> str | None:
    if not item:
        return None
    insights = item.metadata.get("comment_insights") or []
    if not insights:
        return None
    return str(insights[0]).strip() or None


def _source_label(source: str) -> str:
    return SOURCE_LABELS.get(source, source.replace("_", " ").title())


def _truncate(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."
