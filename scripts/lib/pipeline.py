"""v3.0.0 orchestration pipeline."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from shutil import which
from typing import Any

from . import (
    bird_x,
    bluesky,
    dates,
    dedupe,
    entity_extract,
    env,
    grounding,
    hackernews,
    instagram,
    normalize,
    planner,
    polymarket,
    providers,
    query,
    reddit,
    rerank,
    schema,
    signals,
    snippet,
    tiktok,
    truthsocial,
    xai_x,
    xiaohongshu_api,
    youtube_yt,
)
from .cluster import cluster_candidates
from .fusion import weighted_rrf

DEPTH_SETTINGS = {
    "quick": {"per_stream_limit": 6, "pool_limit": 15, "rerank_limit": 12},
    "default": {"per_stream_limit": 12, "pool_limit": 40, "rerank_limit": 40},
    "deep": {"per_stream_limit": 20, "pool_limit": 60, "rerank_limit": 60},
}

SEARCH_ALIAS = {
    "hn": "hackernews",
    "bsky": "bluesky",
    "truth": "truthsocial",
    "web": "grounding",
    "xhs": "xiaohongshu",
}

MAX_SOURCE_FETCHES: dict[str, int] = {"x": 2}

MOCK_AVAILABLE_SOURCES = [
    "reddit",
    "x",
    "youtube",
    "tiktok",
    "instagram",
    "hackernews",
    "bluesky",
    "truthsocial",
    "polymarket",
    "grounding",
    "xiaohongshu",
]


def normalize_requested_sources(sources: list[str] | None) -> list[str] | None:
    if not sources:
        return None
    normalized = []
    for source in sources:
        key = SEARCH_ALIAS.get(source.lower(), source.lower())
        if key not in normalized:
            normalized.append(key)
    return normalized


def available_sources(config: dict[str, Any], requested_sources: list[str] | None = None) -> list[str]:
    google_key = _google_key(config)
    available: list[str] = []
    if config.get("SCRAPECREATORS_API_KEY"):
        available.extend(["reddit", "tiktok", "instagram"])
    if env.get_x_source(config):
        available.append("x")
    if which("yt-dlp"):
        available.append("youtube")
    available.extend(["hackernews", "polymarket"])
    if env.is_bluesky_available(config):
        available.append("bluesky")
    if env.is_truthsocial_available(config):
        available.append("truthsocial")
    if google_key:
        available.append("grounding")
    if requested_sources and "xiaohongshu" in requested_sources and env.is_xiaohongshu_available(config):
        available.append("xiaohongshu")
    return available


def diagnose(config: dict[str, Any], requested_sources: list[str] | None = None) -> dict[str, Any]:
    requested_sources = normalize_requested_sources(requested_sources)
    google_key = _google_key(config)
    return {
        "providers": {
            "google": bool(google_key),
            "openai": bool(config.get("OPENAI_API_KEY")) and config.get("OPENAI_AUTH_STATUS") == env.AUTH_STATUS_OK,
            "xai": bool(config.get("XAI_API_KEY")),
        },
        "reasoning_provider": (config.get("LAST30DAYS_REASONING_PROVIDER") or "auto").lower(),
        "x_backend": env.get_x_source(config),
        "available_sources": available_sources(config, requested_sources),
    }


def run(
    *,
    topic: str,
    config: dict[str, Any],
    depth: str,
    requested_sources: list[str] | None = None,
    mock: bool = False,
    x_handle: str | None = None,
) -> schema.Report:
    settings = DEPTH_SETTINGS[depth]
    requested_sources = normalize_requested_sources(requested_sources)
    from_date, to_date = dates.get_date_range(30)

    if mock:
        runtime = providers.mock_runtime(config, depth)
        reasoning_provider = None
        grounding_provider = None
        available = list(requested_sources or MOCK_AVAILABLE_SOURCES)
    else:
        runtime, reasoning_provider = providers.resolve_runtime(config, depth)
        grounding_provider = _grounding_provider(config, reasoning_provider)
        available = available_sources(config, requested_sources)
        if requested_sources:
            available = [source for source in available if source in requested_sources]
    if not available:
        raise RuntimeError("No sources are available for this run.")

    plan = planner.plan_query(
        topic=topic,
        available_sources=available,
        requested_sources=requested_sources,
        depth=depth,
        provider=None if mock else reasoning_provider,
        model=None if mock else runtime.planner_model,
    )

    bundle = schema.RetrievalBundle(artifacts={"grounding": []})

    # Fix 2: thread-safe set for sources that returned 429
    rate_limited_sources: set[str] = set()
    rate_limit_lock = threading.Lock()

    futures = {}
    # Fix 1: per-source fetch budget
    source_fetch_count: dict[str, int] = {}
    stream_count = sum(
        1
        for subquery in plan.subqueries
        for source in subquery.sources
        if source in available
    )
    max_workers = max(4, min(16, stream_count or 1))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for subquery in plan.subqueries:
            for source in subquery.sources:
                if source not in available:
                    continue
                # Fix 1: enforce per-source fetch cap
                cap = MAX_SOURCE_FETCHES.get(source)
                if cap is not None:
                    current = source_fetch_count.get(source, 0)
                    if current >= cap:
                        continue
                    source_fetch_count[source] = current + 1
                futures[
                    executor.submit(
                        _retrieve_stream,
                        topic=topic,
                        subquery=subquery,
                        source=source,
                        config=config,
                        depth=depth,
                        date_range=(from_date, to_date),
                        runtime=runtime,
                        grounding_provider=grounding_provider,
                        mock=mock,
                        rate_limited_sources=rate_limited_sources,
                        rate_limit_lock=rate_limit_lock,
                    )
                ] = (subquery, source)

        for future in as_completed(futures):
            subquery, source = futures[future]
            try:
                raw_items, artifact = future.result()
                normalized = normalize.normalize_source_items(
                    source,
                    raw_items,
                    from_date,
                    to_date,
                    freshness_mode=plan.freshness_mode,
                )
                normalized = signals.annotate_stream(normalized, subquery.ranking_query, plan.freshness_mode)
                normalized = signals.prune_low_relevance(normalized, source=source)
                normalized = dedupe.dedupe_items(normalized)
                for item in normalized:
                    item.snippet = snippet.extract_best_snippet(item, subquery.ranking_query)
                normalized = normalized[: settings["per_stream_limit"]]
                bundle.items_by_source_and_query[(subquery.label, source)] = normalized
                bundle.items_by_source.setdefault(source, []).extend(normalized)
                if artifact:
                    bundle.artifacts.setdefault("grounding", []).append(artifact)
            except Exception as exc:
                # Fix 2: share 429 signal so pending futures skip this source
                if _is_rate_limit_error(exc):
                    with rate_limit_lock:
                        rate_limited_sources.add(source)
                bundle.errors_by_source[source] = str(exc)

    # Phase 2: supplemental entity-based searches
    _run_supplemental_searches(
        topic=topic,
        bundle=bundle,
        plan=plan,
        config=config,
        depth=depth,
        date_range=(from_date, to_date),
        runtime=runtime,
        mock=mock,
        rate_limited_sources=rate_limited_sources,
        rate_limit_lock=rate_limit_lock,
        x_handle=x_handle,
    )

    # Phase 2b: retry thin sources with simplified query
    _retry_thin_sources(
        topic=topic,
        bundle=bundle,
        plan=plan,
        config=config,
        depth=depth,
        date_range=(from_date, to_date),
        runtime=runtime,
        grounding_provider=grounding_provider,
        mock=mock,
        rate_limited_sources=rate_limited_sources,
        rate_limit_lock=rate_limit_lock,
        settings=settings,
    )

    # Clear errors for sources that returned items despite partial failures.
    # A source that 429'd on one subquery but succeeded on another is not "errored".
    for source in list(bundle.errors_by_source):
        if bundle.items_by_source.get(source):
            del bundle.errors_by_source[source]

    items_by_source = _finalize_items_by_source(bundle.items_by_source)
    candidates = weighted_rrf(bundle.items_by_source_and_query, plan, pool_limit=settings["pool_limit"])
    ranked_candidates = rerank.rerank_candidates(
        topic=topic,
        plan=plan,
        candidates=candidates,
        provider=None if mock else reasoning_provider,
        model=None if mock else runtime.rerank_model,
        shortlist_size=settings["rerank_limit"],
    )
    clusters = cluster_candidates(ranked_candidates, plan)
    warnings = _warnings(items_by_source, ranked_candidates, bundle.errors_by_source)

    return schema.Report(
        topic=topic,
        range_from=from_date,
        range_to=to_date,
        generated_at=datetime.now(timezone.utc).isoformat(),
        provider_runtime=runtime,
        query_plan=plan,
        clusters=clusters,
        ranked_candidates=ranked_candidates,
        items_by_source=items_by_source,
        errors_by_source=bundle.errors_by_source,
        warnings=warnings,
        artifacts=bundle.artifacts,
    )


def _finalize_items_by_source(items_by_source_raw: dict[str, list[schema.SourceItem]]) -> dict[str, list[schema.SourceItem]]:
    finalized = {}
    for source, items in items_by_source_raw.items():
        items = sorted(items, key=lambda item: item.metadata.get("local_rank_score", 0.0), reverse=True)
        finalized[source] = dedupe.dedupe_items(items)
    return finalized


def _warnings(
    items_by_source: dict[str, list[schema.SourceItem]],
    candidates: list[schema.Candidate],
    errors_by_source: dict[str, str],
) -> list[str]:
    warnings: list[str] = []
    if not candidates:
        warnings.append("No candidates survived retrieval and ranking.")
    if len(candidates) < 5:
        warnings.append("Evidence is thin for this topic.")
    top_sources = {
        source
        for candidate in candidates[:5]
        for source in schema.candidate_sources(candidate)
    }
    if len(top_sources) <= 1 and len(candidates) >= 3:
        warnings.append("Top evidence is highly concentrated in one source.")
    if errors_by_source:
        warnings.append(f"Some sources failed: {', '.join(sorted(errors_by_source))}")
    if not items_by_source:
        warnings.append("No source returned usable items.")
    return warnings


def _is_rate_limit_error(exc: Exception) -> bool:
    """Detect 429 rate-limit errors by status code or message text."""
    if hasattr(exc, "status_code") and getattr(exc, "status_code", None) == 429:
        return True
    return "429" in str(exc)


def _run_supplemental_searches(
    *,
    topic: str,
    bundle: schema.RetrievalBundle,
    plan: schema.QueryPlan,
    config: dict[str, Any],
    depth: str,
    date_range: tuple[str, str],
    runtime: schema.ProviderRuntime,
    mock: bool,
    rate_limited_sources: set[str],
    rate_limit_lock: threading.Lock,
    x_handle: str | None = None,
) -> None:
    """Phase 2: extract entities from Phase 1 results, run targeted supplemental searches."""
    if depth == "quick" or mock:
        return

    from_date, to_date = date_range

    # Convert SourceItems to dicts for entity_extract
    x_dicts = [
        {"author_handle": item.author or "", "text": item.body or ""}
        for item in bundle.items_by_source.get("x", [])
    ]
    reddit_dicts = [
        {
            "subreddit": item.container or "",
            "comment_insights": item.metadata.get("comment_insights", []),
            "top_comments": [
                {"excerpt": c.get("excerpt", c.get("text", ""))}
                for c in (item.metadata.get("top_comments") or [])
                if isinstance(c, dict)
            ],
        }
        for item in bundle.items_by_source.get("reddit", [])
    ]

    if not x_dicts and not reddit_dicts and not x_handle:
        return

    entities = entity_extract.extract_entities(
        reddit_dicts, x_dicts,
        max_handles=3, max_subreddits=3,
    )

    handles = entities.get("x_handles", [])

    # Add explicit --x-handle if provided
    if x_handle:
        handle_clean = x_handle.lstrip("@").lower()
        if handle_clean not in [h.lower() for h in handles]:
            handles.insert(0, handle_clean)

    if not handles:
        return

    # Check if X is rate-limited
    if "x" in rate_limited_sources:
        return

    backend = runtime.x_search_backend or env.get_x_source(config)
    if backend != "bird":
        return  # Handle search only works with Bird CLI

    # Collect existing URLs for deduplication
    existing_urls = {
        item.url
        for items in bundle.items_by_source.values()
        for item in items
        if item.url
    }

    try:
        raw_items = bird_x.search_handles(
            handles, topic, from_date, count_per=3,
        )
    except Exception as exc:
        import sys
        print(f"[Pipeline] Phase 2 handle search failed: {exc}", file=sys.stderr)
        return

    if not raw_items:
        return

    # Normalize, score, deduplicate
    normalized = normalize.normalize_source_items(
        "x", raw_items, from_date, to_date,
        freshness_mode=plan.freshness_mode,
    )
    # Deduplicate against Phase 1 URLs
    normalized = [item for item in normalized if item.url not in existing_urls]
    if not normalized:
        return

    ranking_query = plan.subqueries[0].ranking_query if plan.subqueries else topic
    normalized = signals.annotate_stream(normalized, ranking_query, plan.freshness_mode)
    normalized = dedupe.dedupe_items(normalized)
    for item in normalized:
        item.snippet = snippet.extract_best_snippet(item, ranking_query)

    # Merge into bundle under the primary subquery label so fusion picks them up
    bundle.items_by_source.setdefault("x", []).extend(normalized)
    primary_label = plan.subqueries[0].label if plan.subqueries else "primary"
    existing = bundle.items_by_source_and_query.get((primary_label, "x"), [])
    bundle.items_by_source_and_query[(primary_label, "x")] = existing + normalized


def _retry_thin_sources(
    *,
    topic: str,
    bundle: schema.RetrievalBundle,
    plan: schema.QueryPlan,
    config: dict[str, Any],
    depth: str,
    date_range: tuple[str, str],
    runtime: schema.ProviderRuntime,
    grounding_provider: object | None,
    mock: bool,
    rate_limited_sources: set[str],
    rate_limit_lock: threading.Lock,
    settings: dict[str, Any],
) -> None:
    """Retry sources with thin results using simplified core subject query."""
    if depth == "quick":
        return

    thin_sources = [
        source for source, items in bundle.items_by_source.items()
        if len(items) < 3 and source not in bundle.errors_by_source
    ]

    if not thin_sources:
        return

    core = query.extract_core_subject(topic, max_words=3)
    if not core or core.lower() == topic.lower():
        return

    from_date, to_date = date_range

    # Create a retry subquery with the simplified core subject
    retry_subquery = schema.SubQuery(
        label="retry",
        search_query=core,
        ranking_query=f"What recent evidence from the last 30 days matters for {core}?",
        sources=thin_sources,
        weight=0.3,
    )

    for source in thin_sources:
        if source in rate_limited_sources:
            continue
        try:
            raw_items, artifact = _retrieve_stream(
                topic=topic,
                subquery=retry_subquery,
                source=source,
                config=config,
                depth=depth,
                date_range=date_range,
                runtime=runtime,
                grounding_provider=grounding_provider,
                mock=mock,
                rate_limited_sources=rate_limited_sources,
                rate_limit_lock=rate_limit_lock,
            )
            normalized = normalize.normalize_source_items(
                source, raw_items, from_date, to_date,
                freshness_mode=plan.freshness_mode,
            )
            normalized = signals.annotate_stream(normalized, retry_subquery.ranking_query, plan.freshness_mode)
            normalized = signals.prune_low_relevance(normalized, source=source)
            normalized = dedupe.dedupe_items(normalized)
            for item in normalized:
                item.snippet = snippet.extract_best_snippet(item, retry_subquery.ranking_query)
            normalized = normalized[:settings["per_stream_limit"]]

            existing_urls = {item.url for item in bundle.items_by_source.get(source, []) if item.url}
            new_items = [item for item in normalized if item.url not in existing_urls]

            if new_items:
                bundle.items_by_source.setdefault(source, []).extend(new_items)
                primary_label = plan.subqueries[0].label if plan.subqueries else "primary"
                existing = bundle.items_by_source_and_query.get((primary_label, source), [])
                bundle.items_by_source_and_query[(primary_label, source)] = existing + new_items
        except Exception:
            pass  # Don't add errors for retry failures


def _retrieve_stream(
    *,
    topic: str,
    subquery: schema.SubQuery,
    source: str,
    config: dict[str, Any],
    depth: str,
    date_range: tuple[str, str],
    runtime: schema.ProviderRuntime,
    grounding_provider: object | None,
    mock: bool,
    rate_limited_sources: set[str] | None = None,
    rate_limit_lock: threading.Lock | None = None,
) -> tuple[list[dict], dict]:
    # Early exit if source was rate-limited by a sibling future
    if rate_limited_sources is not None and source in rate_limited_sources:
        return [], {}
    from_date, to_date = date_range
    if mock:
        return _mock_stream_results(source, subquery)

    # Adapt search query per source: discussion platforms need shorter queries
    if source == "reddit":
        search_query = query.extract_core_subject(subquery.search_query, max_words=4)
    elif source == "hackernews":
        search_query = query.extract_core_subject(subquery.search_query, max_words=6)
    else:
        search_query = subquery.search_query

    if source == "grounding":
        if not grounding_provider:
            raise RuntimeError("Grounding requested but Google API key is unavailable.")
        return grounding.grounded_search(
            grounding_provider,
            model=runtime.grounding_model,
            topic=topic,
            subquery=subquery,
            date_range=date_range,
            depth=depth,
        )
    if source == "reddit":
        result = reddit.search_and_enrich(
            search_query,
            from_date,
            to_date,
            depth=depth,
            token=config.get("SCRAPECREATORS_API_KEY"),
        )
        return reddit.parse_reddit_response(result), {}
    if source == "x":
        backend = runtime.x_search_backend or env.get_x_source(config)
        if backend == "bird":
            result = bird_x.search_x(search_query, from_date, to_date, depth=depth)
            return bird_x.parse_bird_response(result, query=search_query), {}
        if backend == "xai":
            model = config.get("LAST30DAYS_X_MODEL") or config.get("XAI_MODEL_PIN") or providers.XAI_DEFAULT
            result = xai_x.search_x(
                config["XAI_API_KEY"],
                model,
                search_query,
                from_date,
                to_date,
                depth=depth,
            )
            return xai_x.parse_x_response(result), {}
        raise RuntimeError("No X backend is available.")
    if source == "youtube":
        result = youtube_yt.search_and_transcribe(search_query, from_date, to_date, depth=depth)
        return youtube_yt.parse_youtube_response(result), {}
    if source == "tiktok":
        result = tiktok.search_and_enrich(
            search_query,
            from_date,
            to_date,
            depth=depth,
            token=env.get_tiktok_token(config),
        )
        return tiktok.parse_tiktok_response(result), {}
    if source == "instagram":
        result = instagram.search_and_enrich(
            search_query,
            from_date,
            to_date,
            depth=depth,
            token=env.get_instagram_token(config),
        )
        return instagram.parse_instagram_response(result), {}
    if source == "hackernews":
        result = hackernews.search_hackernews(search_query, from_date, to_date, depth=depth)
        return hackernews.parse_hackernews_response(result, query=search_query), {}
    if source == "bluesky":
        result = bluesky.search_bluesky(search_query, from_date, to_date, depth=depth, config=config)
        return bluesky.parse_bluesky_response(result), {}
    if source == "truthsocial":
        result = truthsocial.search_truthsocial(search_query, from_date, to_date, depth=depth, config=config)
        return truthsocial.parse_truthsocial_response(result), {}
    if source == "polymarket":
        result = polymarket.search_polymarket(search_query, from_date, to_date, depth=depth)
        return polymarket.parse_polymarket_response(result, topic=search_query), {}
    if source == "xiaohongshu":
        return xiaohongshu_api.search_feeds(
            search_query,
            from_date,
            to_date,
            env.get_xiaohongshu_api_base(config),
            depth=depth,
        ), {}
    raise RuntimeError(f"Unsupported source: {source}")


def _google_key(config: dict[str, Any]) -> str | None:
    return config.get("GOOGLE_API_KEY") or config.get("GEMINI_API_KEY") or config.get("GOOGLE_GENAI_API_KEY")


def _grounding_provider(config: dict[str, Any], reasoning_provider: object) -> object | None:
    if isinstance(reasoning_provider, providers.GeminiClient):
        return reasoning_provider
    google_key = _google_key(config)
    if not google_key:
        return None
    return providers.GeminiClient(google_key)


def _mock_stream_results(source: str, subquery: schema.SubQuery) -> tuple[list[dict], dict]:
    payloads = {
        "reddit": [
            {
                "id": "R1",
                "title": f"{subquery.search_query} discussion thread",
                "url": "https://reddit.com/r/example/comments/1",
                "subreddit": "example",
                "date": dates.get_date_range(5)[0],
                "engagement": {"score": 120, "num_comments": 48, "upvote_ratio": 0.91},
                "selftext": f"Community discussion about {subquery.search_query}.",
                "top_comments": [{"excerpt": "Strong firsthand feedback from users."}],
                "relevance": 0.82,
                "why_relevant": "Mock Reddit result",
            }
        ],
        "x": [
            {
                "id": "X1",
                "text": f"People on X are discussing {subquery.search_query} right now.",
                "url": "https://x.com/example/status/1",
                "author_handle": "example",
                "date": dates.get_date_range(2)[0],
                "engagement": {"likes": 200, "reposts": 35, "replies": 18, "quotes": 4},
                "relevance": 0.79,
                "why_relevant": "Mock X result",
            }
        ],
        "grounding": [
            {
                "id": "WG1",
                "title": f"{subquery.search_query} article",
                "url": "https://example.com/article",
                "source_domain": "example.com",
                "snippet": f"Recent web reporting about {subquery.search_query}.",
                "date": dates.get_date_range(7)[0],
                "relevance": 0.88,
                "why_relevant": "Mock grounded web result",
                "metadata": {"searchEntryPoint": {"renderedContent": "mock"}},
            }
        ],
    }
    if source == "grounding":
        return payloads.get(source, []), {
            "label": subquery.label,
            "mock": True,
            "answerText": f"Mock grounded answer for {subquery.search_query}.",
            "webSearchQueries": [subquery.search_query],
            "groundingChunks": [],
            "groundingSupports": [],
        }
    return payloads.get(source, []), {}
