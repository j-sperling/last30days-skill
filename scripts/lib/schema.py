"""Core data model for the v3.0.0 last30days pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any


def _drop_none(value: Any) -> Any:
    """Recursively remove None values from dataclass-derived structures."""
    if is_dataclass(value):
        return _drop_none(asdict(value))
    if isinstance(value, dict):
        cleaned = {
            key: _drop_none(item)
            for key, item in value.items()
            if item is not None
        }
        return cleaned
    if isinstance(value, list):
        return [_drop_none(item) for item in value]
    return value


@dataclass
class ProviderRuntime:
    """Resolved runtime provider selection."""

    reasoning_provider: str
    planner_model: str
    rerank_model: str
    grounding_model: str
    x_search_backend: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _drop_none(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProviderRuntime":
        return cls(
            reasoning_provider=payload["reasoning_provider"],
            planner_model=payload["planner_model"],
            rerank_model=payload["rerank_model"],
            grounding_model=payload["grounding_model"],
            x_search_backend=payload.get("x_search_backend"),
        )


@dataclass
class SubQuery:
    """Planner-emitted retrieval unit."""

    label: str
    search_query: str
    ranking_query: str
    sources: list[str]
    weight: float = 1.0

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SubQuery":
        return cls(
            label=payload["label"],
            search_query=payload["search_query"],
            ranking_query=payload["ranking_query"],
            sources=list(payload.get("sources") or []),
            weight=float(payload.get("weight") or 1.0),
        )


@dataclass
class QueryPlan:
    """Planner output."""

    intent: str
    freshness_mode: str
    cluster_mode: str
    raw_topic: str
    subqueries: list[SubQuery]
    source_weights: dict[str, float]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _drop_none(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "QueryPlan":
        return cls(
            intent=payload["intent"],
            freshness_mode=payload["freshness_mode"],
            cluster_mode=payload["cluster_mode"],
            raw_topic=payload["raw_topic"],
            subqueries=[SubQuery.from_dict(item) for item in payload.get("subqueries") or []],
            source_weights=dict(payload.get("source_weights") or {}),
            notes=list(payload.get("notes") or []),
        )


@dataclass
class SourceItem:
    """Generic normalized evidence item."""

    item_id: str
    source: str
    title: str
    body: str
    url: str
    author: str | None = None
    container: str | None = None
    published_at: str | None = None
    date_confidence: str = "low"
    engagement: dict[str, float | int] = field(default_factory=dict)
    relevance_hint: float = 0.5
    why_relevant: str = ""
    snippet: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _drop_none(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SourceItem":
        return cls(
            item_id=payload["item_id"],
            source=payload["source"],
            title=payload["title"],
            body=payload.get("body") or "",
            url=payload.get("url") or "",
            author=payload.get("author"),
            container=payload.get("container"),
            published_at=payload.get("published_at"),
            date_confidence=payload.get("date_confidence") or "low",
            engagement=dict(payload.get("engagement") or {}),
            relevance_hint=float(payload.get("relevance_hint") or 0.5),
            why_relevant=payload.get("why_relevant") or "",
            snippet=payload.get("snippet") or "",
            metadata=dict(payload.get("metadata") or {}),
        )


@dataclass
class Candidate:
    """Global candidate after fusion and reranking."""

    candidate_id: str
    item_id: str
    source: str
    title: str
    url: str
    snippet: str
    subquery_labels: list[str]
    native_ranks: dict[str, int]
    local_relevance: float
    freshness: int
    engagement: int | None
    source_quality: float
    rrf_score: float
    rerank_score: float | None = None
    final_score: float = 0.0
    explanation: str | None = None
    cluster_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _drop_none(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Candidate":
        return cls(
            candidate_id=payload["candidate_id"],
            item_id=payload["item_id"],
            source=payload["source"],
            title=payload["title"],
            url=payload.get("url") or "",
            snippet=payload.get("snippet") or "",
            subquery_labels=list(payload.get("subquery_labels") or []),
            native_ranks={key: int(value) for key, value in (payload.get("native_ranks") or {}).items()},
            local_relevance=float(payload.get("local_relevance") or 0.0),
            freshness=int(payload.get("freshness") or 0),
            engagement=payload.get("engagement"),
            source_quality=float(payload.get("source_quality") or 0.0),
            rrf_score=float(payload.get("rrf_score") or 0.0),
            rerank_score=float(payload["rerank_score"]) if payload.get("rerank_score") is not None else None,
            final_score=float(payload.get("final_score") or 0.0),
            explanation=payload.get("explanation"),
            cluster_id=payload.get("cluster_id"),
            metadata=dict(payload.get("metadata") or {}),
        )


@dataclass
class Cluster:
    """Ranked cluster of related candidates."""

    cluster_id: str
    title: str
    candidate_ids: list[str]
    representative_ids: list[str]
    sources: list[str]
    score: float
    uncertainty: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _drop_none(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Cluster":
        return cls(
            cluster_id=payload["cluster_id"],
            title=payload["title"],
            candidate_ids=list(payload.get("candidate_ids") or []),
            representative_ids=list(payload.get("representative_ids") or []),
            sources=list(payload.get("sources") or []),
            score=float(payload.get("score") or 0.0),
            uncertainty=payload.get("uncertainty"),
        )


@dataclass
class Report:
    """Final pipeline output."""

    topic: str
    range_from: str
    range_to: str
    generated_at: str
    provider_runtime: ProviderRuntime
    query_plan: QueryPlan
    clusters: list[Cluster]
    ranked_candidates: list[Candidate]
    items_by_source: dict[str, list[SourceItem]]
    errors_by_source: dict[str, str]
    warnings: list[str] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _drop_none(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Report":
        return cls(
            topic=payload["topic"],
            range_from=payload["range_from"],
            range_to=payload["range_to"],
            generated_at=payload["generated_at"],
            provider_runtime=ProviderRuntime.from_dict(payload["provider_runtime"]),
            query_plan=QueryPlan.from_dict(payload["query_plan"]),
            clusters=[Cluster.from_dict(item) for item in payload.get("clusters") or []],
            ranked_candidates=[Candidate.from_dict(item) for item in payload.get("ranked_candidates") or []],
            items_by_source={
                source: [SourceItem.from_dict(item) for item in items]
                for source, items in (payload.get("items_by_source") or {}).items()
            },
            errors_by_source=dict(payload.get("errors_by_source") or {}),
            warnings=list(payload.get("warnings") or []),
            artifacts=dict(payload.get("artifacts") or {}),
        )


def to_dict(value: Any) -> Any:
    """Serialize dataclasses and nested containers."""
    return _drop_none(value)
