# /last30days v3.0.0

`last30days` is a hard-cut rewrite of the recency research skill. The old heuristic-heavy, source-first stack is gone. The new runtime is a planner-driven retrieval pipeline with Gemini `3.1` preview grounding, weighted reciprocal rank fusion, snippet-first reranking, and cluster-first output.

## What changed in v3.0.0

- Replaced source-bucket ranking with a true global candidate pool.
- Replaced generic web backends with Gemini Google Search grounding.
- Replaced multi-factor heuristic ranking with:
  - local deterministic signals
  - weighted RRF fusion
  - single-score reranking
- Replaced loose cross-source links with real clusters.
- Removed legacy modules:
  - `query_type.py`
  - `cache.py`
  - `models.py`
  - `score.py`
  - `openai_reddit.py`
  - `scrapecreators_x.py`
  - `brave_search.py`
  - `parallel_search.py`
  - `openrouter_search.py`
  - `websearch.py`

## Architecture

1. Query planner
2. Per-`(subquery, source)` retrieval
3. Normalization and within-source dedupe
4. Best-snippet extraction for long items
5. Weighted RRF fusion
6. Single-score rerank
7. Cluster formation plus representative selection
8. Cluster-first rendering

The main data model lives in [scripts/lib/schema.py](/Users/js/projects/last30days-skill/scripts/lib/schema.py). The orchestrator lives in [scripts/lib/pipeline.py](/Users/js/projects/last30days-skill/scripts/lib/pipeline.py).

## Runtime providers

Gemini `3.1` preview is the required Gemini runtime:

- planner default: `gemini-3.1-flash-lite-preview`
- rerank quick/default: `gemini-3.1-flash-lite-preview`
- rerank deep: `gemini-3.1-pro-preview`
- grounding: `gemini-3.1-flash-lite-preview`

OpenAI and xAI remain supported as fallback reasoning providers, but grounded web retrieval always stays on Gemini `3.1` preview.

## Supported sources

- Reddit
- X
- YouTube
- TikTok
- Instagram
- Hacker News
- Bluesky
- Truth Social
- Polymarket
- Gemini grounded web
- Xiaohongshu

Availability depends on credentials and local tools.

## Configuration

Core environment variables:

```bash
GOOGLE_API_KEY=...
SCRAPECREATORS_API_KEY=...
OPENAI_API_KEY=...
XAI_API_KEY=...
BSKY_HANDLE=...
BSKY_APP_PASSWORD=...
TRUTHSOCIAL_TOKEN=...
AUTH_TOKEN=...
CT0=...
LAST30DAYS_REASONING_PROVIDER=auto
LAST30DAYS_PLANNER_MODEL=gemini-3.1-flash-lite-preview
LAST30DAYS_RERANK_MODEL=gemini-3.1-flash-lite-preview
LAST30DAYS_GROUNDING_MODEL=gemini-3.1-flash-lite-preview
LAST30DAYS_X_BACKEND=xai
```

## CLI

```bash
python3 scripts/last30days.py "codex vs claude code"
python3 scripts/last30days.py "anthropic odds" --emit=json
python3 scripts/last30days.py "best react animation libraries" --quick
python3 scripts/last30days.py "ai coding agents" --deep --search=reddit,x,grounding
python3 scripts/last30days.py --diagnose
```

Emit modes:

- `compact`
- `md`
- `json`
- `context`

## Development

Run the mock pipeline:

```bash
python3 scripts/last30days.py "test topic" --mock --emit=compact
python3 -m unittest discover -s tests -p 'test_*.py'
```

After edits, deploy the skill adapters:

```bash
bash scripts/sync.sh
```
