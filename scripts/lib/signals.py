"""Reusable local scoring signals for v3 pipeline stages."""

from __future__ import annotations

import math

from . import dates, relevance, schema

# Editorial signal-to-noise scores. Grounding (Google Search) is 1.0 baseline;
# social platforms discounted for noise.
SOURCE_QUALITY = {
    "xiaohongshu": 0.7,
    "hackernews": 0.8,
    "youtube": 0.85,
    "reddit": 0.6,
    "x": 0.68,
    "bluesky": 0.66,
    "truthsocial": 0.6,
    "polymarket": 0.5,
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


def log1p_safe(value: float | int | None) -> float:
    if value is None:
        return 0.0
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    if numeric <= 0:
        return 0.0
    return math.log1p(numeric)


def _top_comment_score(item: schema.SourceItem) -> float:
    comments = item.metadata.get("top_comments") or []
    if not comments or not isinstance(comments[0], dict):
        return 0.0
    return log1p_safe(comments[0].get("score"))


# Per-source engagement weights: list of (field_name, weight) tuples.
# Reddit uses a custom function because upvote_ratio and top_comment_score
# are not simple log1p fields.
ENGAGEMENT_WEIGHTS: dict[str, list[tuple[str, float]]] = {
    "x":            [("likes", 0.55), ("reposts", 0.25), ("replies", 0.15), ("quotes", 0.05)],
    "youtube":      [("views", 0.50), ("likes", 0.35), ("comments", 0.15)],
    "tiktok":       [("views", 0.50), ("likes", 0.30), ("comments", 0.20)],
    "instagram":    [("views", 0.50), ("likes", 0.30), ("comments", 0.20)],
    "hackernews":   [("points", 0.55), ("comments", 0.45)],
    "bluesky":      [("likes", 0.40), ("reposts", 0.30), ("replies", 0.20), ("quotes", 0.10)],
    "truthsocial":  [("likes", 0.45), ("reposts", 0.30), ("replies", 0.25)],
    "polymarket":   [("volume", 0.60), ("liquidity", 0.40)],
}


def _weighted_engagement(item: schema.SourceItem, weights: list[tuple[str, float]]) -> float | None:
    values = [(log1p_safe(item.engagement.get(field)), weight) for field, weight in weights]
    if not any(v for v, _ in values):
        return None
    return sum(v * w for v, w in values)


def _reddit_engagement(item: schema.SourceItem) -> float | None:
    score = log1p_safe(item.engagement.get("score"))
    comments = log1p_safe(item.engagement.get("num_comments"))
    ratio = float(item.engagement.get("upvote_ratio") or 0.0)
    top_comment = _top_comment_score(item)
    if not any([score, comments, ratio, top_comment]):
        return None
    return (0.50 * score) + (0.35 * comments) + (0.05 * (ratio * 10.0)) + (0.10 * top_comment)


def _generic_engagement(item: schema.SourceItem) -> float | None:
    if not item.engagement:
        return None
    values = [logged for v in item.engagement.values() if (logged := log1p_safe(v)) > 0]
    if not values:
        return None
    return sum(values) / len(values)


def engagement_raw(item: schema.SourceItem) -> float | None:
    if item.source == "reddit":
        return _reddit_engagement(item)
    weights = ENGAGEMENT_WEIGHTS.get(item.source)
    if weights:
        return _weighted_engagement(item, weights)
    return _generic_engagement(item)


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
    """Attach local scoring metadata and return items sorted by local_rank_score."""
    engagement_scores = normalize([engagement_raw(item) for item in items])
    for item, eng_score in zip(items, engagement_scores, strict=True):
        item.local_relevance = local_relevance(item, ranking_query)
        item.freshness = freshness(item, freshness_mode)
        item.engagement_score = eng_score
        item.source_quality = source_quality(item.source)
        item.local_rank_score = (
            0.65 * item.local_relevance
            + 0.25 * (item.freshness / 100.0)
            + 0.10 * ((eng_score or 0) / 100.0)
        )
    return sorted(items, key=lambda item: item.local_rank_score or 0, reverse=True)


def prune_low_relevance(
    items: list[schema.SourceItem],
    minimum: float = 0.15,
) -> list[schema.SourceItem]:
    """Drop weak lexical matches when stronger evidence exists."""
    filtered = [
        item
        for item in items
        if (item.local_relevance if item.local_relevance is not None else 0.0) >= minimum
    ]
    return filtered or items
