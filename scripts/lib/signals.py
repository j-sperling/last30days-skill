"""Reusable local scoring signals for v3 pipeline stages."""

from __future__ import annotations

import math

from . import dates, relevance, schema

SOURCE_QUALITY = {
    "grounding": 1.0,
    "xiaohongshu": 0.7,
    "polymarket": 0.9,
    "hackernews": 0.8,
    "youtube": 0.75,
    "reddit": 0.7,
    "x": 0.68,
    "bluesky": 0.66,
    "truthsocial": 0.6,
    "instagram": 0.58,
    "tiktok": 0.58,
}


def source_quality(source: str) -> float:
    return SOURCE_QUALITY.get(source, 0.6)


def local_relevance(item: schema.SourceItem, ranking_query: str) -> float:
    text = "\n".join(
        part
        for part in [item.title, item.body, item.snippet]
        if part
    )
    hashtags = item.metadata.get("hashtags") if isinstance(item.metadata, dict) else None
    return relevance.token_overlap_relevance(ranking_query, text, hashtags=hashtags)


def freshness(item: schema.SourceItem, freshness_mode: str = "balanced_recent") -> int:
    score = dates.recency_score(item.published_at)
    if freshness_mode == "strict_recent":
        return int(score)
    if freshness_mode == "evergreen_ok":
        return int((score * 0.6) + 40)
    return int((score * 0.8) + 10)


def engagement_raw(item: schema.SourceItem) -> float | None:
    if not item.engagement:
        return None
    values = []
    for value in item.engagement.values():
        if value is None:
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if numeric <= 0:
            continue
        values.append(math.log1p(numeric))
    if not values:
        return None
    return sum(values) / len(values)


def normalize(values: list[float | None]) -> list[int | None]:
    valid = [value for value in values if value is not None]
    if not valid:
        return [None for _ in values]
    low = min(valid)
    high = max(valid)
    if math.isclose(low, high):
        return [50 if value is not None else None for value in values]
    return [
        None
        if value is None
        else int(((value - low) / (high - low)) * 100)
        for value in values
    ]


def annotate_stream(
    items: list[schema.SourceItem],
    ranking_query: str,
    freshness_mode: str,
) -> list[schema.SourceItem]:
    """Attach local scoring metadata for a single retrieval stream."""
    engagement_scores = normalize([engagement_raw(item) for item in items])
    for item, engagement_score in zip(items, engagement_scores, strict=True):
        item.metadata["local_relevance"] = local_relevance(item, ranking_query)
        item.metadata["freshness"] = freshness(item, freshness_mode)
        item.metadata["engagement_score"] = engagement_score
        item.metadata["source_quality"] = source_quality(item.source)
        item.metadata["local_rank_score"] = (
            0.55 * item.metadata["local_relevance"]
            + 0.25 * (item.metadata["freshness"] / 100.0)
            + 0.20 * ((engagement_score or 0) / 100.0)
        )
    return sorted(items, key=lambda item: item.metadata["local_rank_score"], reverse=True)
