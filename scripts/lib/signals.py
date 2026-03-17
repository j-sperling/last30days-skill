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


def _reddit_engagement(item: schema.SourceItem) -> float | None:
    score = log1p_safe(item.engagement.get("score"))
    comments = log1p_safe(item.engagement.get("num_comments"))
    ratio = float(item.engagement.get("upvote_ratio") or 0.0)
    top_comment = _top_comment_score(item)
    if not any([score, comments, ratio, top_comment]):
        return None
    return (0.50 * score) + (0.35 * comments) + (0.05 * (ratio * 10.0)) + (0.10 * top_comment)


def _x_engagement(item: schema.SourceItem) -> float | None:
    likes = log1p_safe(item.engagement.get("likes"))
    reposts = log1p_safe(item.engagement.get("reposts"))
    replies = log1p_safe(item.engagement.get("replies"))
    quotes = log1p_safe(item.engagement.get("quotes"))
    if not any([likes, reposts, replies, quotes]):
        return None
    return (0.55 * likes) + (0.25 * reposts) + (0.15 * replies) + (0.05 * quotes)


def _youtube_engagement(item: schema.SourceItem) -> float | None:
    views = log1p_safe(item.engagement.get("views"))
    likes = log1p_safe(item.engagement.get("likes"))
    comments = log1p_safe(item.engagement.get("comments"))
    if not any([views, likes, comments]):
        return None
    return (0.50 * views) + (0.35 * likes) + (0.15 * comments)


def _short_video_engagement(item: schema.SourceItem) -> float | None:
    views = log1p_safe(item.engagement.get("views"))
    likes = log1p_safe(item.engagement.get("likes"))
    comments = log1p_safe(item.engagement.get("comments"))
    if not any([views, likes, comments]):
        return None
    return (0.50 * views) + (0.30 * likes) + (0.20 * comments)


def _hackernews_engagement(item: schema.SourceItem) -> float | None:
    points = log1p_safe(item.engagement.get("points"))
    comments = log1p_safe(item.engagement.get("comments"))
    if not any([points, comments]):
        return None
    return (0.55 * points) + (0.45 * comments)


def _bluesky_engagement(item: schema.SourceItem) -> float | None:
    likes = log1p_safe(item.engagement.get("likes"))
    reposts = log1p_safe(item.engagement.get("reposts"))
    replies = log1p_safe(item.engagement.get("replies"))
    quotes = log1p_safe(item.engagement.get("quotes"))
    if not any([likes, reposts, replies, quotes]):
        return None
    return (0.40 * likes) + (0.30 * reposts) + (0.20 * replies) + (0.10 * quotes)


def _truthsocial_engagement(item: schema.SourceItem) -> float | None:
    likes = log1p_safe(item.engagement.get("likes"))
    reposts = log1p_safe(item.engagement.get("reposts"))
    replies = log1p_safe(item.engagement.get("replies"))
    if not any([likes, reposts, replies]):
        return None
    return (0.45 * likes) + (0.30 * reposts) + (0.25 * replies)


def _polymarket_engagement(item: schema.SourceItem) -> float | None:
    volume = log1p_safe(item.engagement.get("volume"))
    liquidity = log1p_safe(item.engagement.get("liquidity"))
    if not any([volume, liquidity]):
        return None
    return (0.60 * volume) + (0.40 * liquidity)


def _generic_engagement(item: schema.SourceItem) -> float | None:
    if not item.engagement:
        return None
    values = []
    for value in item.engagement.values():
        logged = log1p_safe(value)
        if logged > 0:
            values.append(logged)
    if not values:
        return None
    return sum(values) / len(values)


def engagement_raw(item: schema.SourceItem) -> float | None:
    dispatch = {
        "reddit": _reddit_engagement,
        "x": _x_engagement,
        "youtube": _youtube_engagement,
        "tiktok": _short_video_engagement,
        "instagram": _short_video_engagement,
        "hackernews": _hackernews_engagement,
        "bluesky": _bluesky_engagement,
        "truthsocial": _truthsocial_engagement,
        "polymarket": _polymarket_engagement,
    }
    return dispatch.get(item.source, _generic_engagement)(item)


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
            0.75 * item.metadata["local_relevance"]
            + 0.20 * (item.metadata["freshness"] / 100.0)
            + 0.05 * ((engagement_score or 0) / 100.0)
        )
    return sorted(items, key=lambda item: item.metadata["local_rank_score"], reverse=True)


def prune_low_relevance(
    items: list[schema.SourceItem],
    minimum: float = 0.1,
) -> list[schema.SourceItem]:
    """Drop obviously weak lexical matches when stronger evidence exists."""
    filtered = [
        item
        for item in items
        if float(item.metadata.get("local_relevance") or 0.0) >= minimum
    ]
    return filtered or items
