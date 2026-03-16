"""Candidate clustering and representative selection."""

from __future__ import annotations

from . import dedupe, schema

CLUSTERABLE_INTENTS = {"breaking_news", "opinion", "comparison", "prediction"}


def _candidate_text(candidate: schema.Candidate) -> str:
    return " ".join(part for part in [candidate.title, candidate.snippet] if part).strip()


def _mmr_representatives(
    candidates: list[schema.Candidate],
    limit: int = 3,
    diversity_lambda: float = 0.75,
) -> list[str]:
    selected: list[schema.Candidate] = []
    remaining = list(candidates)
    while remaining and len(selected) < limit:
        if not selected:
            best = max(remaining, key=lambda candidate: candidate.final_score)
            selected.append(best)
            remaining.remove(best)
            continue

        def score(candidate: schema.Candidate) -> float:
            diversity_penalty = max(
                dedupe.hybrid_similarity(_candidate_text(candidate), _candidate_text(existing))
                for existing in selected
            )
            return (diversity_lambda * candidate.final_score) - ((1 - diversity_lambda) * diversity_penalty * 100)

        best = max(remaining, key=score)
        selected.append(best)
        remaining.remove(best)
    return [candidate.candidate_id for candidate in selected]


def cluster_candidates(
    candidates: list[schema.Candidate],
    plan: schema.QueryPlan,
) -> list[schema.Cluster]:
    """Greedy clustering around high-ranked leaders."""
    if plan.intent not in CLUSTERABLE_INTENTS or plan.cluster_mode == "none":
        clusters = []
        for index, candidate in enumerate(candidates, start=1):
            cluster_id = f"cluster-{index}"
            candidate.cluster_id = cluster_id
            clusters.append(
                schema.Cluster(
                    cluster_id=cluster_id,
                    title=candidate.title,
                    candidate_ids=[candidate.candidate_id],
                    representative_ids=[candidate.candidate_id],
                    sources=[candidate.source],
                    score=candidate.final_score,
                    uncertainty=None,
                )
            )
        return clusters

    groups: list[list[schema.Candidate]] = []
    threshold = 0.42 if plan.intent == "breaking_news" else 0.48
    for candidate in candidates:
        assigned = False
        for group in groups:
            leader = group[0]
            similarity = dedupe.hybrid_similarity(_candidate_text(candidate), _candidate_text(leader))
            if similarity >= threshold:
                group.append(candidate)
                assigned = True
                break
        if not assigned:
            groups.append([candidate])

    clusters: list[schema.Cluster] = []
    for index, group in enumerate(groups, start=1):
        group.sort(key=lambda candidate: candidate.final_score, reverse=True)
        cluster_id = f"cluster-{index}"
        representatives = _mmr_representatives(group)
        for candidate in group:
            candidate.cluster_id = cluster_id
        clusters.append(
            schema.Cluster(
                cluster_id=cluster_id,
                title=group[0].title,
                candidate_ids=[candidate.candidate_id for candidate in group],
                representative_ids=representatives,
                sources=sorted({candidate.source for candidate in group}),
                score=max(candidate.final_score for candidate in group),
                uncertainty=_cluster_uncertainty(group),
            )
        )

    return sorted(clusters, key=lambda cluster: cluster.score, reverse=True)


def _cluster_uncertainty(group: list[schema.Candidate]) -> str | None:
    if len(group) == 1:
        return "single-source"
    sources = {candidate.source for candidate in group}
    if len(sources) == 1:
        return "single-source"
    if max(candidate.final_score for candidate in group) < 55:
        return "thin-evidence"
    return None
