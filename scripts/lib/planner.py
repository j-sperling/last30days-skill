"""LLM-first query planning with deterministic guards for risky queries."""

from __future__ import annotations

import re

from . import query, schema

ALLOWED_INTENTS = {
    "factual",
    "product",
    "concept",
    "opinion",
    "how_to",
    "comparison",
    "breaking_news",
    "prediction",
}
ALLOWED_CLUSTER_MODES = {"none", "story", "workflow", "market", "debate"}
QUICK_SOURCE_PRIORITY = {
    "factual": ["grounding", "hackernews", "reddit", "x", "youtube", "polymarket"],
    "product": ["reddit", "grounding", "x", "youtube", "hackernews", "polymarket"],
    "concept": ["grounding", "hackernews", "reddit", "x", "youtube", "polymarket"],
    "opinion": ["reddit", "x", "grounding", "youtube", "hackernews", "polymarket"],
    "how_to": ["grounding", "reddit", "youtube", "x", "hackernews", "polymarket"],
    "comparison": ["reddit", "x", "grounding", "hackernews", "youtube", "polymarket"],
    "breaking_news": ["grounding", "x", "reddit", "hackernews", "youtube", "polymarket"],
    "prediction": ["polymarket", "x", "grounding", "reddit", "hackernews", "youtube"],
}
SOURCE_PRIORITY = {
    "factual": ["grounding", "hackernews", "reddit", "x", "youtube", "polymarket"],
    "product": ["reddit", "grounding", "x", "youtube", "hackernews", "polymarket"],
    "concept": ["grounding", "hackernews", "reddit", "x", "youtube", "polymarket"],
    "opinion": ["reddit", "x", "grounding", "youtube", "hackernews", "polymarket"],
    "how_to": ["grounding", "youtube", "reddit", "x", "hackernews", "polymarket"],
    "comparison": ["reddit", "x", "grounding", "hackernews", "youtube", "polymarket"],
    "breaking_news": ["grounding", "x", "reddit", "hackernews", "youtube", "polymarket"],
    "prediction": ["polymarket", "x", "grounding", "hackernews", "reddit", "youtube"],
}
SOURCE_LIMITS = {
    "quick": {
        "factual": 2,
        "product": 2,
        "concept": 2,
        "opinion": 2,
        "how_to": 2,
        "comparison": 2,
        "breaking_news": 2,
        "prediction": 2,
    },
    "default": {
        "factual": 2,
        "product": 3,
        "concept": 3,
        "opinion": 3,
        "how_to": 3,
        "comparison": 3,
        "breaking_news": 4,
        "prediction": 3,
    },
}
SOURCE_CAPABILITIES = {
    "grounding": {"web", "reference"},
    "reddit": {"discussion", "social"},
    "x": {"discussion", "social"},
    "youtube": {"video", "video_longform", "discussion"},
    "tiktok": {"video", "video_shortform", "social"},
    "instagram": {"video", "video_shortform", "social"},
    "hackernews": {"discussion", "link"},
    "bluesky": {"discussion", "social"},
    "truthsocial": {"discussion", "social"},
    "polymarket": {"market"},
    "xiaohongshu": {"video", "video_shortform", "social"},
}
DEFAULT_INTENT_CAPABILITIES = {
    "comparison": {"discussion", "video", "web", "reference", "social", "link"},
    "how_to": {"discussion", "video", "web", "reference", "link"},
}
MAX_SUBQUERIES = 4


def plan_query(
    *,
    topic: str,
    available_sources: list[str],
    requested_sources: list[str] | None,
    depth: str,
    provider: object | None,
    model: str | None,
) -> schema.QueryPlan:
    """Create a query plan, preferring the configured reasoning provider."""
    if _should_force_deterministic_plan(topic):
        return _fallback_plan(
            topic,
            available_sources,
            requested_sources,
            depth,
            note="deterministic-comparison-plan",
        )
    prompt = _build_prompt(topic, available_sources, requested_sources, depth)
    if provider and model:
        try:
            raw = provider.generate_json(model, prompt)
            plan = _sanitize_plan(raw, topic, available_sources, requested_sources, depth)
            if plan.subqueries:
                return plan
        except Exception:
            pass
    return _fallback_plan(topic, available_sources, requested_sources, depth)


def _build_prompt(
    topic: str,
    available_sources: list[str],
    requested_sources: list[str] | None,
    depth: str,
) -> str:
    requested = ", ".join(requested_sources or ["auto"])
    available = ", ".join(available_sources)
    return f"""
You are the query planner for a live last-30-days research pipeline.

Topic: {topic}
Depth: {depth}
Available sources: {available}
Requested sources: {requested}

Return JSON only with this shape:
{{
  "intent": "factual|product|concept|opinion|how_to|comparison|breaking_news|prediction",
  "freshness_mode": "strict_recent|balanced_recent|evergreen_ok",
  "cluster_mode": "none|story|workflow|market|debate",
  "source_weights": {{"source_name": 0.0}},
  "subqueries": [
    {{
      "label": "short label",
      "search_query": "keyword style query for search APIs",
      "ranking_query": "natural language rewrite for reranking",
      "sources": ["reddit", "x", "grounding"],
      "weight": 1.0
    }}
  ],
  "notes": ["optional short notes"]
}}

Rules:
- emit 1 to 4 subqueries
- every subquery must include both search_query and ranking_query
- sources must be drawn from Available sources only
- use cluster_mode=none for factual or many how-to queries
- use strict_recent for breaking news and most predictions
- use debate for comparison/opinion, market for prediction, workflow for how_to, story for breaking_news
- search_query should be concise and keyword-heavy
- ranking_query should read like a natural-language question
- preserve exact proper nouns and entity strings from the topic
""".strip()


def _sanitize_plan(
    raw: dict,
    topic: str,
    available_sources: list[str],
    requested_sources: list[str] | None,
    depth: str,
) -> schema.QueryPlan:
    intent_hint = str(raw.get("intent") or _infer_intent(topic)).strip()
    if intent_hint not in ALLOWED_INTENTS:
        intent_hint = _infer_intent(topic)
    requested = set(requested_sources or [])
    available = set(available_sources)
    eligible_sources = [
        source for source in available_sources
        if (not requested or source in requested)
    ]
    source_weights = {
        source: float(weight)
        for source, weight in (raw.get("source_weights") or {}).items()
        if source in available
    }
    if requested:
        source_weights = {source: weight for source, weight in source_weights.items() if source in requested}
    if not source_weights:
        source_weights = _default_source_weights(_infer_intent(topic), available_sources)
    elif depth == "default" and intent_hint in DEFAULT_INTENT_CAPABILITIES:
        for source in _default_sources_for_intent(intent_hint, eligible_sources):
            source_weights.setdefault(source, 1.0)
    source_weights = _normalize_weights(source_weights)

    subqueries: list[schema.SubQuery] = []
    for index, subquery in enumerate((raw.get("subqueries") or [])[:_max_subqueries(intent_hint)], start=1):
        if not isinstance(subquery, dict):
            continue
        sources = [source for source in subquery.get("sources") or [] if source in source_weights]
        if requested:
            sources = [source for source in sources if source in requested]
        if not sources:
            sources = list(source_weights)
        search_query = str(subquery.get("search_query") or "").strip()
        ranking_query = str(subquery.get("ranking_query") or "").strip()
        if not search_query or not ranking_query:
            continue
        subqueries.append(
            schema.SubQuery(
                label=str(subquery.get("label") or f"q{index}").strip() or f"q{index}",
                search_query=search_query,
                ranking_query=ranking_query,
                sources=sources,
                weight=max(0.05, float(subquery.get("weight") or 1.0)),
            )
        )
    if depth == "quick" and subqueries:
        subqueries = subqueries[:1]
    if not subqueries:
        return _fallback_plan(topic, available_sources, requested_sources, depth)

    intent = intent_hint
    freshness_mode = str(raw.get("freshness_mode") or _default_freshness(intent)).strip()
    if intent == "how_to":
        freshness_mode = "evergreen_ok"
    cluster_mode = str(raw.get("cluster_mode") or _default_cluster_mode(intent)).strip()
    if cluster_mode not in ALLOWED_CLUSTER_MODES:
        cluster_mode = _default_cluster_mode(intent)

    return schema.QueryPlan(
        intent=intent,
        freshness_mode=freshness_mode,
        cluster_mode=cluster_mode,
        raw_topic=topic,
        subqueries=_normalize_subquery_weights(_trim_subqueries_for_depth(subqueries, intent, depth, eligible_sources)),
        source_weights=source_weights,
        notes=[str(note).strip() for note in raw.get("notes") or [] if str(note).strip()],
    )


def _normalize_subquery_weights(subqueries: list[schema.SubQuery]) -> list[schema.SubQuery]:
    total = sum(subquery.weight for subquery in subqueries) or 1.0
    return [
        schema.SubQuery(
            label=subquery.label,
            search_query=subquery.search_query,
            ranking_query=subquery.ranking_query,
            sources=subquery.sources,
            weight=subquery.weight / total,
        )
        for subquery in subqueries
    ]


def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    total = sum(max(weight, 0.0) for weight in weights.values()) or 1.0
    return {
        source: max(weight, 0.0) / total
        for source, weight in weights.items()
    }


def _trim_subqueries_for_depth(
    subqueries: list[schema.SubQuery],
    intent: str,
    depth: str,
    available_sources: list[str],
) -> list[schema.SubQuery]:
    limits = SOURCE_LIMITS.get(depth)
    if not limits:
        return subqueries
    if depth == "default" and intent in DEFAULT_INTENT_CAPABILITIES:
        expanded_sources = _default_sources_for_intent(intent, available_sources)
        return [
            schema.SubQuery(
                label=subquery.label,
                search_query=subquery.search_query,
                ranking_query=subquery.ranking_query,
                sources=expanded_sources,
                weight=subquery.weight,
            )
            for subquery in subqueries
        ]
    priority_table = QUICK_SOURCE_PRIORITY if depth == "quick" else SOURCE_PRIORITY
    priority = priority_table.get(intent, priority_table["breaking_news"])
    limit = limits.get(intent, 3)
    ranked_sources = [source for source in priority if source in available_sources]
    if not ranked_sources:
        ranked_sources = list(available_sources)
    trimmed = []
    for subquery in subqueries:
        if depth in {"quick", "default"}:
            preferred_sources = ranked_sources[:limit]
        else:
            preferred_sources = [source for source in ranked_sources if source in subquery.sources][:limit]
            if len(preferred_sources) < limit:
                for source in ranked_sources:
                    if source in preferred_sources:
                        continue
                    preferred_sources.append(source)
                    if len(preferred_sources) >= limit:
                        break
        trimmed.append(
            schema.SubQuery(
                label=subquery.label,
                search_query=subquery.search_query,
                ranking_query=subquery.ranking_query,
                sources=preferred_sources,
                weight=subquery.weight,
            )
        )
    return trimmed


def _fallback_plan(
    topic: str,
    available_sources: list[str],
    requested_sources: list[str] | None,
    depth: str,
    note: str = "fallback-plan",
) -> schema.QueryPlan:
    intent = _infer_intent(topic)
    allowed_sources = requested_sources or available_sources
    source_weights = _default_source_weights(intent, allowed_sources)
    core = query.extract_core_subject(topic, max_words=6, strip_suffixes=True)
    base_search = _keyword_query(topic, core)
    base_ranking = _ranking_query(topic, core)

    subqueries = [schema.SubQuery(
        label="primary",
        search_query=base_search,
        ranking_query=base_ranking,
        sources=list(source_weights),
        weight=1.0,
    )]

    if depth != "quick" and intent == "comparison":
        entities = _comparison_entities(topic)
        if entities:
            for index, entity in enumerate(entities, start=1):
                subqueries.append(
                    schema.SubQuery(
                        label=f"entity-{index}",
                        search_query=entity,
                        ranking_query=f"What recent evidence from the last 30 days is most relevant to {entity} in the comparison '{topic}'?",
                        sources=list(source_weights),
                        weight=0.65,
                    )
                )
    elif depth != "quick" and intent == "prediction":
        subqueries.append(
            schema.SubQuery(
                label="odds",
                search_query=f"{base_search} odds forecast",
                ranking_query=f"What are the current odds, forecasts, or market signals about {topic}?",
                sources=[source for source in source_weights if source in {"polymarket", "grounding", "x", "reddit"}] or list(source_weights),
                weight=0.7,
            )
        )
    elif depth != "quick" and intent == "breaking_news":
        subqueries.append(
            schema.SubQuery(
                label="reaction",
                search_query=f"{base_search} reaction update",
                ranking_query=f"What new reactions or follow-up reporting from the last 30 days matter for {topic}?",
                sources=[source for source in source_weights if source in {"x", "reddit", "grounding", "hackernews"}] or list(source_weights),
                weight=0.7,
            )
        )

    return schema.QueryPlan(
        intent=intent,
        freshness_mode=_default_freshness(intent),
        cluster_mode=_default_cluster_mode(intent),
        raw_topic=topic,
        subqueries=_normalize_subquery_weights(
            _trim_subqueries_for_depth(subqueries[:_max_subqueries(intent)], intent, depth, list(source_weights))
        ),
        source_weights=_normalize_weights(source_weights),
        notes=[note],
    )


def _infer_intent(topic: str) -> str:
    text = topic.lower().strip()
    if re.search(r"\b(vs|versus|compare|compared to|difference between)\b", text):
        return "comparison"
    # Slash-separated capitalized words: "React/Vue/Svelte" (but not URLs)
    if not re.search(r"https?://", topic) and re.search(r"\b[A-Za-z]+/[A-Za-z]+\b", topic):
        return "comparison"
    if re.search(r"\b(odds|predict|prediction|forecast|chance|probability|will .* win)\b", text):
        return "prediction"
    if re.search(r"\b(how to|tutorial|guide|setup|step by step|deploy|install)\b", text):
        return "how_to"
    if re.search(r"\b(what is|what are|who is|who acquired|when did|parameter count|release date)\b", text):
        return "factual"
    if re.search(r"\b(thoughts on|worth it|should i|opinion|review)\b", text):
        return "opinion"
    if re.search(r"\b(latest|news|announced|just shipped|launched|released|update)\b", text):
        return "breaking_news"
    if re.search(r"\b(pricing|feature|features|best .* for|top .* for)\b", text):
        return "product"
    if re.search(r"\b(explain|concept|protocol|architecture|what does)\b", text):
        return "concept"
    return "breaking_news"


def _default_freshness(intent: str) -> str:
    if intent in {"breaking_news", "prediction"}:
        return "strict_recent"
    if intent in {"concept", "how_to"}:
        return "evergreen_ok"
    return "balanced_recent"


def _default_cluster_mode(intent: str) -> str:
    return {
        "breaking_news": "story",
        "comparison": "debate",
        "opinion": "debate",
        "prediction": "market",
        "how_to": "workflow",
        "factual": "none",
        "product": "none",
        "concept": "none",
    }.get(intent, "none")


def _default_source_weights(intent: str, sources: list[str]) -> dict[str, float]:
    base = {source: 1.0 for source in sources}
    if intent == "prediction":
        for source, bonus in {"polymarket": 2.5, "grounding": 1.6, "x": 1.3}.items():
            if source in base:
                base[source] += bonus
    elif intent == "breaking_news":
        for source, bonus in {"grounding": 2.0, "x": 1.5, "reddit": 1.3, "hackernews": 0.8}.items():
            if source in base:
                base[source] += bonus
    elif intent == "how_to":
        for source, bonus in {"youtube": 2.0, "grounding": 1.4, "hackernews": 0.8}.items():
            if source in base:
                base[source] += bonus
    elif intent == "factual":
        for source, bonus in {"grounding": 2.5, "reddit": 0.8, "x": 0.5}.items():
            if source in base:
                base[source] += bonus
    return base


def _keyword_query(topic: str, core: str) -> str:
    compounds = query.extract_compound_terms(topic)
    quoted = " ".join(f"\"{term}\"" for term in compounds[:2])
    keywords = [quoted.strip(), core.strip() or topic.strip()]
    return " ".join(part for part in keywords if part).strip()


def _ranking_query(topic: str, core: str) -> str:
    if topic.strip().endswith("?"):
        return topic.strip()
    if core and core.lower() != topic.lower():
        return f"What recent evidence from the last 30 days is most relevant to {topic}, especially about {core}?"
    return f"What recent evidence from the last 30 days is most relevant to {topic}?"


_TRAILING_CONTEXT = re.compile(
    r"\s+\b(?:for|in|on|at|to|with|about|from|by|during|since|after|before|using|via)\b.*$",
    re.I,
)


def _comparison_entities(topic: str) -> list[str]:
    # "difference between X and Y" -> "X vs Y" (replace "and" only in this context)
    normalized = re.sub(
        r"\bdifference between\s+(.+?)\s+and\s+",
        r"\1 vs ",
        topic,
        flags=re.I,
    )
    normalized = re.sub(r"\b(compared to)\b", " vs ", normalized, flags=re.I)
    parts = [
        part.strip(" \t\r\n?.,:;!()[]{}\"'")
        for part in re.split(r"\bvs\.?\b|\bversus\b|/", normalized, flags=re.I)
        if part.strip(" \t\r\n?.,:;!()[]{}\"'")
    ]
    # Strip trailing context from parts ("Svelte for frontend in 2026" -> "Svelte")
    if len(parts) >= 2:
        parts = [_TRAILING_CONTEXT.sub("", part).strip() or part for part in parts]
        deduped = []
        for part in parts:
            if part and part not in deduped:
                deduped.append(part)
        return deduped[:_max_subqueries("comparison")]
    return []


def _should_force_deterministic_plan(topic: str) -> bool:
    return _infer_intent(topic) == "comparison" and len(_comparison_entities(topic)) >= 2


def _max_subqueries(intent: str) -> int:
    return MAX_SUBQUERIES if intent == "comparison" else 3


def _default_sources_for_intent(intent: str, available_sources: list[str]) -> list[str]:
    if intent == "comparison":
        target_capabilities = DEFAULT_INTENT_CAPABILITIES.get(intent)
        matched = [
            source
            for source in available_sources
            if SOURCE_CAPABILITIES.get(source, set()) & (target_capabilities or set())
        ]
        return matched or list(available_sources)

    if intent == "how_to":
        selected: set[str] = set()
        capability_groups = [
            ({"web", "reference"}, True),
            ({"video_longform"}, False),
            ({"video"}, False),
            ({"discussion"}, True),
        ]
        for group, required in capability_groups:
            if not required and selected & {
                source for source in available_sources if SOURCE_CAPABILITIES.get(source, set()) & {"video", "video_longform"}
            }:
                continue
            for source in available_sources:
                if source in selected:
                    continue
                if SOURCE_CAPABILITIES.get(source, set()) & group:
                    selected.add(source)
                    break
        if not selected:
            return list(available_sources)
        return [source for source in available_sources if source in selected]

    target_capabilities = DEFAULT_INTENT_CAPABILITIES.get(intent)
    if not target_capabilities:
        return list(available_sources)
    matched = [
        source
        for source in available_sources
        if SOURCE_CAPABILITIES.get(source, set()) & target_capabilities
    ]
    return matched or list(available_sources)
