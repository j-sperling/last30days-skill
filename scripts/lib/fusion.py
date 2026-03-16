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
            item_local_relevance = float(item.metadata.get("local_relevance", item.relevance_hint))
            item_freshness = int(item.metadata.get("freshness", 0))
            item_source_quality = float(item.metadata.get("source_quality", 0.6))
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
                    local_relevance=item_local_relevance,
                    freshness=item_freshness,
                    engagement=item.metadata.get("engagement_score"),
                    source_quality=item_source_quality,
                    rrf_score=score,
                    sources=[item.source],
                    source_items=[item],
                    metadata={
                        "provenance": [
                            {
                                "source": source,
                                "subquery_label": label,
                                "native_rank": rank,
                                "item_id": item.item_id,
                            }
                        ]
                    },
                )
                continue

            candidate = candidates[key]
            candidate.rrf_score += score
            previous_primary_score = (candidate.local_relevance * 100.0) + candidate.freshness + (candidate.source_quality * 10.0)
            incoming_primary_score = (item_local_relevance * 100.0) + item_freshness + (item_source_quality * 10.0)
            candidate.local_relevance = max(
                candidate.local_relevance,
                item_local_relevance,
            )
            candidate.freshness = max(candidate.freshness, item_freshness)
            if candidate.engagement is None:
                candidate.engagement = item.metadata.get("engagement_score")
            elif item.metadata.get("engagement_score") is not None:
                candidate.engagement = max(candidate.engagement, item.metadata["engagement_score"])
            candidate.source_quality = max(
                candidate.source_quality,
                item_source_quality,
            )
            candidate.native_ranks[f"{label}:{source}"] = rank
            if label not in candidate.subquery_labels:
                candidate.subquery_labels.append(label)
            if item.source not in candidate.sources:
                candidate.sources.append(item.source)
            if not any(existing.source == item.source and existing.item_id == item.item_id for existing in candidate.source_items):
                candidate.source_items.append(item)
            candidate.metadata.setdefault("provenance", []).append(
                {
                    "source": source,
                    "subquery_label": label,
                    "native_rank": rank,
                    "item_id": item.item_id,
                }
            )
            if incoming_primary_score > previous_primary_score:
                candidate.item_id = item.item_id
                candidate.source = item.source
                candidate.title = item.title
                candidate.snippet = item.snippet
            if len(candidate.snippet.split()) < len(item.snippet.split()):
                candidate.snippet = item.snippet

    fused = sorted(
        candidates.values(),
        key=lambda candidate: (
            -candidate.rrf_score,
            -candidate.local_relevance,
            -candidate.freshness,
            schema.candidate_source_label(candidate),
            candidate.title,
        ),
    )
    return fused[:pool_limit]
