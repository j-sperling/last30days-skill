"""Reranking with LLM-scored relevance and demotion of low-confidence candidates."""

from __future__ import annotations

from . import schema

INTENT_SCORING_HINTS: dict[str, str] = {
    "comparison": (
        "Prefer items that directly compare, contrast, or benchmark the entities"
        " mentioned in the topic. Head-to-head comparisons score higher than items"
        " covering only one entity."
    ),
    "how_to": (
        "Prefer tutorials, step-by-step guides, and practical demonstrations."
        " Video walkthroughs and code examples score higher than theoretical discussion."
    ),
    "prediction": (
        "Prefer items with quantitative forecasts, odds, market data, or expert"
        " predictions. Vague speculation scores lower."
    ),
    "factual": (
        "Prefer items with specific facts, dates, numbers, and primary sources."
        " News reports with direct quotes score higher than commentary."
    ),
    "opinion": (
        "Prefer items with substantive opinions backed by reasoning or evidence."
        " Hot takes without substance score lower."
    ),
    "breaking_news": (
        "Prefer the latest updates, eyewitness reports, and official statements."
        " Recency matters more than depth."
    ),
    "concept": (
        "Prefer clear explanations with examples or analogies. Accessible content"
        " scores higher than dense academic papers unless the topic is highly technical."
    ),
    "product": (
        "Prefer hands-on reviews, benchmarks, and user experience reports."
        " Marketing copy and listicles score lower."
    ),
}


def rerank_candidates(
    *,
    topic: str,
    plan: schema.QueryPlan,
    candidates: list[schema.Candidate],
    provider: object | None,
    model: str | None,
    shortlist_size: int,
) -> list[schema.Candidate]:
    """Rerank the fused shortlist, demoting candidates the reranker scored as irrelevant."""
    shortlisted = candidates[:shortlist_size]
    if provider and model and shortlisted:
        try:
            response = provider.generate_json(model, _build_prompt(topic, plan, shortlisted))
            _apply_llm_scores(shortlisted, response)
        except Exception as exc:
            import sys
            print(f"[Rerank] LLM reranking failed, using local fallback: {type(exc).__name__}: {exc}", file=sys.stderr)
            _apply_fallback_scores(shortlisted)
    else:
        _apply_fallback_scores(shortlisted)

    if len(candidates) > shortlist_size:
        tail = candidates[shortlist_size:]
        _apply_fallback_scores(tail)

    return sorted(
        candidates,
        key=lambda candidate: (
            -candidate.final_score,
            -(candidate.engagement or -1),
            min(candidate.native_ranks.values()),
            candidate.title,
        ),
    )


def _intent_hint_block(plan: schema.QueryPlan) -> str:
    hint = INTENT_SCORING_HINTS.get(plan.intent, "")
    if hint:
        return f"\nIntent-specific guidance ({plan.intent}):\n- {hint}\n"
    return ""


def _build_prompt(topic: str, plan: schema.QueryPlan, candidates: list[schema.Candidate]) -> str:
    ranking_queries = "\n".join(
        f"- {subquery.label}: {subquery.ranking_query}"
        for subquery in plan.subqueries
    )
    candidate_block = "\n".join(
        "\n".join(
            [
                f"- candidate_id: {candidate.candidate_id}",
                f"  sources: {schema.candidate_source_label(candidate)}",
                f"  title: {candidate.title[:220]}",
                f"  snippet: {candidate.snippet[:420]}",
                f"  date: {schema.candidate_best_published_at(candidate) or 'unknown'}",
                f"  matched_subqueries: {', '.join(candidate.subquery_labels)}",
            ]
        )
        for candidate in candidates
    )
    return f"""
Judge search-result relevance for a last-30-days research pipeline.

Topic: {topic}
Intent: {plan.intent}
Ranking queries:
{ranking_queries}

Return JSON only:
{{
  "scores": [
    {{
      "candidate_id": "id",
      "relevance": 0-100,
      "reason": "short reason"
    }}
  ]
}}

Scoring guidance:
- 90 to 100: one of the strongest pieces of evidence
- 70 to 89: clearly relevant and useful
- 40 to 69: somewhat relevant but weaker
- 0 to 39: weak, redundant, or off-target
{_intent_hint_block(plan)}
Candidates:
{candidate_block}
""".strip()


def _apply_llm_scores(candidates: list[schema.Candidate], payload: dict) -> None:
    scores = {}
    for row in payload.get("scores") or []:
        if not isinstance(row, dict):
            continue
        candidate_id = str(row.get("candidate_id") or "").strip()
        if not candidate_id:
            continue
        scores[candidate_id] = (
            max(0.0, min(100.0, float(row.get("relevance") or 0.0))),
            str(row.get("reason") or "").strip() or None,
        )
    for candidate in candidates:
        rerank_score, reason = scores.get(candidate.candidate_id, _fallback_tuple(candidate))
        candidate.rerank_score = rerank_score
        candidate.explanation = reason
        candidate.final_score = _final_score(candidate)


def _apply_fallback_scores(candidates: list[schema.Candidate]) -> None:
    for candidate in candidates:
        rerank_score, reason = _fallback_tuple(candidate)
        candidate.rerank_score = rerank_score
        candidate.explanation = reason
        candidate.final_score = _final_score(candidate)


def _fallback_tuple(candidate: schema.Candidate) -> tuple[float, str]:
    score = (
        (candidate.local_relevance * 100.0 * 0.7)
        + (candidate.freshness * 0.2)
        + (candidate.source_quality * 100.0 * 0.1)
    )
    return max(0.0, min(100.0, score)), "fallback-local-score"


def _final_score(candidate: schema.Candidate) -> float:
    normalized_rrf = _normalized_rrf(candidate.rrf_score)
    rerank_score = candidate.rerank_score or 0.0
    base = (
        0.65 * rerank_score
        + 0.20 * normalized_rrf
        + 0.10 * candidate.freshness
        + 0.05 * (candidate.source_quality * 100.0)
    )
    if candidate.rerank_score is not None and candidate.rerank_score < 5.0:
        base *= 0.3
    return base


def _normalized_rrf(rrf_score: float) -> float:
    # Practical bound for the shortlist sizes we use.
    return max(0.0, min(100.0, (rrf_score / 0.08) * 100.0))
