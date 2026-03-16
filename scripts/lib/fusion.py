"""Weighted reciprocal rank fusion for per-(subquery, source) streams."""

from __future__ import annotations

from . import schema

RRF_K = 60


def candidate_key(item: schema.SourceItem) -> str:
    if item.url:
        return item.url.strip()
    return f"{item.source}:{item.item_id}"


def weighted_rrf(
    streams: dict[tuple[str, str], list[schema.SourceItem]],
    plan: schema.QueryPlan,
    *,
    pool_limit: int,
) -> list[schema.Candidate]:
    """Fuse ranked lists into a single candidate pool."""
    subqueries = {subquery.label: subquery for subquery in plan.subqueries}
    candidates: dict[str, schema.Candidate] = {}

    for (label, source), items in streams.items():
        subquery = subqueries[label]
        weight = subquery.weight * plan.source_weights.get(source, 1.0)
        for rank, item in enumerate(items, start=1):
            key = candidate_key(item)
            score = weight / (RRF_K + rank)
            if key not in candidates:
                candidates[key] = schema.Candidate(
                    candidate_id=key,
                    item_id=item.item_id,
                    source=item.source,
                    title=item.title,
                    url=item.url,
                    snippet=item.snippet,
                    subquery_labels=[label],
                    native_ranks={f"{label}:{source}": rank},
                    local_relevance=float(item.metadata.get("local_relevance", item.relevance_hint)),
                    freshness=int(item.metadata.get("freshness", 0)),
                    engagement=item.metadata.get("engagement_score"),
                    source_quality=float(item.metadata.get("source_quality", 0.6)),
                    rrf_score=score,
                    metadata={"item": item.to_dict()},
                )
                continue

            candidate = candidates[key]
            candidate.rrf_score += score
            candidate.local_relevance = max(
                candidate.local_relevance,
                float(item.metadata.get("local_relevance", item.relevance_hint)),
            )
            candidate.freshness = max(candidate.freshness, int(item.metadata.get("freshness", 0)))
            if candidate.engagement is None:
                candidate.engagement = item.metadata.get("engagement_score")
            elif item.metadata.get("engagement_score") is not None:
                candidate.engagement = max(candidate.engagement, item.metadata["engagement_score"])
            candidate.source_quality = max(
                candidate.source_quality,
                float(item.metadata.get("source_quality", 0.6)),
            )
            candidate.native_ranks[f"{label}:{source}"] = rank
            if label not in candidate.subquery_labels:
                candidate.subquery_labels.append(label)
            if len(candidate.snippet.split()) < len(item.snippet.split()):
                candidate.snippet = item.snippet

    fused = sorted(
        candidates.values(),
        key=lambda candidate: (
            -candidate.rrf_score,
            -candidate.local_relevance,
            -candidate.freshness,
            candidate.source,
            candidate.title,
        ),
    )
    return fused[:pool_limit]
