# How Search Works in v3.0.0

`last30days` no longer runs a source-first pipeline. The v3 runtime is one ranked evidence pipeline that pulls from multiple live sources, fuses them, and renders clusters.

## Pipeline

```text
topic
  -> provider resolution
  -> query planner
  -> per-(subquery, source) retrieval
  -> normalization
  -> within-source dedupe and local signals
  -> snippet extraction
  -> weighted RRF fusion
  -> single-score rerank
  -> clustering and representative selection
  -> compact / json / context output
```

Core modules:

- [scripts/lib/providers.py](/Users/js/projects/last30days-skill/scripts/lib/providers.py)
- [scripts/lib/planner.py](/Users/js/projects/last30days-skill/scripts/lib/planner.py)
- [scripts/lib/pipeline.py](/Users/js/projects/last30days-skill/scripts/lib/pipeline.py)
- [scripts/lib/fusion.py](/Users/js/projects/last30days-skill/scripts/lib/fusion.py)
- [scripts/lib/rerank.py](/Users/js/projects/last30days-skill/scripts/lib/rerank.py)
- [scripts/lib/cluster.py](/Users/js/projects/last30days-skill/scripts/lib/cluster.py)

## Providers

Gemini `3.1` preview is the default reasoning runtime:

- planner: `gemini-3.1-flash-lite-preview`
- rerank `quick` / `default`: `gemini-3.1-flash-lite-preview`
- rerank `deep`: `gemini-3.1-pro-preview`
- web retrieval: Brave Search (preferred) or Serper

OpenAI and xAI can still provide planner and rerank responses when configured. X search can use xAI or Bird cookie auth. Public web retrieval now uses Brave or Serper and drops undated web hits.

## Query planning

The planner emits:

- `intent`
- `freshness_mode`
- `cluster_mode`
- `source_weights`
- 1 to 3 `subqueries`

Each subquery contains:

- `label`
- `search_query`
- `ranking_query`
- `sources`
- `weight`

Quick and default modes clamp source selection by intent. Deep mode keeps the broader mix.

## Retrieval

Retrieval runs per `(subquery, source)` pair, not just per source.

Supported live sources:

- grounded web
- Reddit
- X
- YouTube
- TikTok
- Instagram
- Hacker News
- Bluesky
- Truth Social
- Polymarket
- Xiaohongshu

Each source adapter is responsible for API interaction only. Ranking policy happens later in the shared pipeline.

## Normalization and snippets

Every source payload becomes a common `SourceItem` in [schema.py](/Users/js/projects/last30days-skill/scripts/lib/schema.py). The pipeline then:

- filters by the requested date range
- computes local relevance, freshness, engagement, and source-quality signals
- dedupes within each retrieval stream
- extracts a best-match snippet for reranking

Grounded web items are required to have a usable in-window date before they survive normalization.

## Fusion and reranking

First-stage fusion uses weighted reciprocal rank fusion over the per-stream ranked lists. The fused pool becomes `Candidate` objects with:

- combined provenance
- preserved per-source items
- fused `rrf_score`
- local scoring signals

Reranking is intentionally simple. The reranker assigns one relevance score per candidate, then combines:

- rerank score
- normalized RRF
- freshness
- source quality

This avoids the heavier multi-axis LLM scoring that v3 explicitly removed.

## Clustering and rendering

The ranked candidates are grouped into clusters for story-like and debate-like intents. The renderer then outputs:

- cluster-first markdown for `compact` / `md`
- the full machine-readable report for `json`
- a shorter synthesis context for `context`

The default output is no longer a source dump.

## Depth profiles

- `--quick`: lowest latency, narrowest source mix, minimal enrichment
- default: balanced recall and latency
- `--deep`: broader retrieval and heavier enrichment

Quick mode exists so agents can iterate fast without paying the full enrichment cost on every pass. Default and deep preserve richer retrieval for harder topics.
