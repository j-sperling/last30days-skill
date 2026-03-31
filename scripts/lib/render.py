"""Cluster-first rendering for the v3 pipeline."""

from __future__ import annotations

from collections import Counter

from . import dates, schema

SOURCE_LABELS = {
    "grounding": "Web",
    "hackernews": "Hacker News",
    "truthsocial": "Truth Social",
    "xiaohongshu": "Xiaohongshu",
    "x": "X",
}

SOURCE_EMOJI: dict[str, str] = {
    "reddit": "\U0001f7e0",
    "x": "\U0001f535",
    "youtube": "\U0001f534",
    "tiktok": "\U0001f3b5",
    "instagram": "\U0001f4f8",
    "hackernews": "\U0001f7e1",
    "bluesky": "\U0001f98b",
    "truthsocial": "\U0001f1fa\U0001f1f8",
    "polymarket": "\U0001f4ca",
    "grounding": "\U0001f310",
    "xiaohongshu": "\U0001f4d5",
}

SOURCE_NOUN: dict[str, tuple[str, str]] = {
    "reddit": ("thread", "threads"),
    "x": ("post", "posts"),
    "youtube": ("video", "videos"),
    "tiktok": ("video", "videos"),
    "instagram": ("reel", "reels"),
    "hackernews": ("story", "stories"),
    "bluesky": ("post", "posts"),
    "truthsocial": ("post", "posts"),
    "polymarket": ("market", "markets"),
    "grounding": ("page", "pages"),
    "xiaohongshu": ("note", "notes"),
}


def render_compact(report: schema.Report, cluster_limit: int = 8, quality: dict | None = None) -> str:
    non_empty = [s for s, items in sorted(report.items_by_source.items()) if items]
    lines = [
        f"# last30days: {report.topic}",
        "",
        f"- Date range: {report.range_from} to {report.range_to}",
        f"- Sources: {len(non_empty)} active ({', '.join(_source_label(s) for s in non_empty)})" if non_empty else "- Sources: none",
        "",
    ]

    freshness_warning = _assess_data_freshness(report)
    lines.append("## What I learned")
    lines.append("")
    candidate_by_id = {candidate.candidate_id: candidate for candidate in report.ranked_candidates}
    clusters = report.clusters[:cluster_limit]
    if not clusters:
        lines.append("- I did not find enough usable recent evidence to support a confident answer yet.")
        lines.append("")
    else:
        for cluster in clusters:
            lines.extend(_render_cluster(cluster, candidate_by_id))

    lines.extend(_render_stats_tree(report))
    lines.extend(_render_coverage_notes(report, freshness_warning=freshness_warning, quality=quality))
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


def _render_cluster(
    cluster: schema.Cluster,
    candidate_by_id: dict[str, schema.Candidate],
) -> list[str]:
    lines = [f"### {cluster.title}"]
    cluster_note = _cluster_note(cluster)
    if cluster_note:
        lines.append(f"- {cluster_note}")
    for candidate_id in cluster.representative_ids:
        candidate = candidate_by_id.get(candidate_id)
        if not candidate:
            continue
        lines.extend(_render_candidate(candidate))
    lines.append("")
    return lines


def _render_candidate(candidate: schema.Candidate) -> list[str]:
    primary = schema.candidate_primary_item(candidate)
    detail_parts = [_source_label(candidate.source), _format_actor(primary), _format_brief_date(primary)]
    engagement = _format_engagement(primary)
    if engagement:
        detail_parts.append(engagement.strip("[]"))
    details = "; ".join(part for part in detail_parts if part)
    lines = [f"- {candidate.title}{f' ({details})' if details else ''}"]
    corroboration = _format_corroboration(candidate)
    if corroboration:
        lines.append(f"  - {corroboration}")
    explanation = _format_explanation(candidate)
    if explanation:
        lines.append(f"  - Why it matters: {explanation}")
    if candidate.snippet:
        lines.append(f"  - Evidence: {_truncate(candidate.snippet, 360)}")
    top_comment = _top_comment_excerpt(primary)
    if top_comment:
        lines.append(f"  - Top comment: {_truncate(top_comment, 240)}")
    insight = _comment_insight(primary)
    if insight:
        lines.append(f"  - Insight: {_truncate(insight, 220)}")
    highlights = _transcript_highlights(primary)
    if highlights:
        for hl in highlights:
            lines.append(f'  - Transcript highlight: "{_truncate(hl, 200)}"')
    return lines


def _render_stats_tree(report: schema.Report) -> list[str]:
    lines = [
        "## Stats",
        "",
    ]
    non_empty_sources = {
        source: items
        for source, items in sorted(report.items_by_source.items())
        if items
    }
    if not non_empty_sources:
        lines.append("- No usable source metrics were available for this run.")
        lines.append("")
        return lines

    active_sources = ", ".join(
        f"{_source_label(source)} ({_count_noun(source, len(items))})"
        for source, items in non_empty_sources.items()
    )
    lines.append(f"- Active sources: {active_sources}")

    for source, items in non_empty_sources.items():
        parts = [f"{_count_noun(source, len(items))}"]
        engagement_summary = _aggregate_engagement(source, items)
        if engagement_summary:
            parts.append(engagement_summary)
        actor_summary = _top_actor_summary(source, items)
        if actor_summary:
            parts.append(actor_summary)
        lines.append(f"- {_source_label(source)}: {'; '.join(parts)}")

    top_voices = _top_voices_overall(non_empty_sources)
    if top_voices:
        lines.append(f"- Top voices: {', '.join(top_voices)}")
    lines.append("")
    return lines


def _render_coverage_notes(
    report: schema.Report,
    *,
    freshness_warning: str | None,
    quality: dict | None,
) -> list[str]:
    notes: list[str] = []
    if freshness_warning:
        notes.append(freshness_warning)

    notes.extend(report.warnings)

    zero_sources = [
        source
        for source in report.query_plan.source_weights
        if not report.items_by_source.get(source) and source not in report.errors_by_source
    ]
    if zero_sources:
        labels = [_source_label(source) for source in zero_sources]
        notes.append(f"No usable items surfaced from {_join_labels(labels)}.")

    for source, error in sorted(report.errors_by_source.items()):
        notes.append(f"{_source_label(source)} had an error: {error}")

    if quality and quality.get("nudge_text"):
        notes.extend(line.strip() for line in quality["nudge_text"].splitlines() if line.strip())

    if not notes:
        return []

    lines = ["## Coverage notes", ""]
    lines.extend(f"- {note}" for note in notes)
    lines.append("")
    return lines


def _count_noun(source: str, count: int) -> str:
    singular, plural = SOURCE_NOUN.get(source, ("item", "items"))
    return f"{count} {singular if count == 1 else plural}"


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
        if (_days_ago := dates.days_ago(item.published_at)) is not None and _days_ago <= 7
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


def _format_brief_date(item: schema.SourceItem | None) -> str | None:
    if not item or not item.published_at:
        return None
    if item.date_confidence == "high":
        return item.published_at
    if item.date_confidence == "low":
        return f"{item.published_at} (approx. date)"
    return f"{item.published_at} (inferred date)"


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


# Per-source engagement display fields: list of (field_name, label) tuples.
ENGAGEMENT_DISPLAY: dict[str, list[tuple[str, str]]] = {
    "reddit":       [("score", "pts"), ("num_comments", "cmt")],
    "x":            [("likes", "likes"), ("reposts", "rt"), ("replies", "re")],
    "youtube":      [("views", "views"), ("likes", "likes"), ("comments", "cmt")],
    "tiktok":       [("views", "views"), ("likes", "likes"), ("comments", "cmt")],
    "instagram":    [("views", "views"), ("likes", "likes"), ("comments", "cmt")],
    "hackernews":   [("points", "pts"), ("comments", "cmt")],
    "bluesky":      [("likes", "likes"), ("reposts", "rt"), ("replies", "re")],
    "truthsocial":  [("likes", "likes"), ("reposts", "rt"), ("replies", "re")],
    "polymarket":   [("volume", "vol"), ("liquidity", "liq")],
}


def _format_engagement(item: schema.SourceItem | None) -> str | None:
    if not item or not item.engagement:
        return None
    engagement = item.engagement
    fields = ENGAGEMENT_DISPLAY.get(item.source)
    if fields:
        text = _fmt_pairs([(engagement.get(field), label) for field, label in fields])
    else:
        # Generic fallback: engagement.items() yields (key, value) but
        # _fmt_pairs expects (value, label), so swap them.
        text = _fmt_pairs([(value, key) for key, value in list(engagement.items())[:3]])
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


def _aggregate_engagement(source: str, items: list[schema.SourceItem]) -> str | None:
    fields = ENGAGEMENT_DISPLAY.get(source)
    if not fields:
        return None
    totals: list[tuple[float | int | None, str]] = []
    for field, label in fields:
        total = 0
        found = False
        for item in items:
            value = item.engagement.get(field)
            if value in (None, ""):
                continue
            found = True
            total += value
        totals.append((total if found else None, label))
    return _fmt_pairs(totals) or None


def _top_actor_summary(source: str, items: list[schema.SourceItem]) -> str | None:
    actors = _top_actors_for_source(source, items)
    if not actors:
        return None
    label = {
        "reddit": "communities",
        "grounding": "domains",
        "youtube": "channels",
        "hackernews": "domains",
    }.get(source, "voices")
    return f"{label}: {', '.join(actors)}"


def _top_actors_for_source(source: str, items: list[schema.SourceItem], limit: int = 3) -> list[str]:
    counts: Counter[str] = Counter()
    for item in items:
        actor = _stats_actor(item)
        if actor:
            counts[actor] += 1
    return [actor for actor, _ in counts.most_common(limit)]


def _top_voices_overall(items_by_source: dict[str, list[schema.SourceItem]], limit: int = 5) -> list[str]:
    counts: Counter[str] = Counter()
    for items in items_by_source.values():
        for item in items:
            actor = _stats_actor(item)
            if actor:
                counts[actor] += 1
    return [actor for actor, _ in counts.most_common(limit)]


def _stats_actor(item: schema.SourceItem) -> str | None:
    if item.source == "reddit" and item.container:
        return f"r/{item.container}"
    if item.source in {"x", "bluesky", "truthsocial"} and item.author:
        return f"@{item.author.lstrip('@')}"
    if item.source == "grounding" and item.container:
        return item.container
    if item.source == "youtube" and item.author:
        return item.author
    if item.container and item.container != "Polymarket":
        return item.container
    if item.author:
        return item.author
    return None


def _format_corroboration(candidate: schema.Candidate) -> str | None:
    corroborating = [
        _source_label(source)
        for source in schema.candidate_sources(candidate)
        if source != candidate.source
    ]
    if not corroborating:
        return None
    return f"Also seen in: {', '.join(corroborating)}"


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


def _transcript_highlights(item: schema.SourceItem | None) -> list[str]:
    if not item or item.source != "youtube":
        return []
    return (item.metadata.get("transcript_highlights") or [])[:5]


def _source_label(source: str) -> str:
    return SOURCE_LABELS.get(source, source.replace("_", " ").title())


def _cluster_note(cluster: schema.Cluster) -> str | None:
    if cluster.uncertainty == "single-source":
        return "Limited recent data: this theme showed up on one source."
    if cluster.uncertainty == "thin-evidence":
        return "Limited recent data: only a small amount of evidence supported this theme."
    return None


def _join_labels(labels: list[str], limit: int = 4) -> str:
    if not labels:
        return ""
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]} and {labels[1]}"
    if len(labels) <= limit:
        return f"{', '.join(labels[:-1])}, and {labels[-1]}"
    head = ", ".join(labels[: limit - 1])
    return f"{head}, and {len(labels) - (limit - 1)} more sources"


def _truncate(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."
