# last30days v3.0.0

`last30days` is a live recency-research skill for the last 30 days. It searches across social, market, and grounded web sources, fuses everything into one ranked pool, and renders evidence clusters instead of source buckets.

The current runtime is a hard-cut v3 pipeline:

1. Query planning
2. Per-`(subquery, source)` retrieval
3. Normalization and within-source dedupe
4. Snippet extraction for long evidence
5. Weighted reciprocal rank fusion
6. Single-score reranking
7. Cluster formation and representative selection
8. Cluster-first rendering

## Runtime

Gemini `3.1` preview is the primary runtime:

- planner: `gemini-3.1-flash-lite-preview`
- rerank `quick` / `default`: `gemini-3.1-flash-lite-preview`
- rerank `deep`: `gemini-3.1-pro-preview`
- Google Search grounding: `gemini-3.1-flash-lite-preview`

OpenAI and xAI are still supported as fallback reasoning providers. X retrieval can use xAI or Bird cookie auth. Public web retrieval is grounded through Gemini.

## Sources

Potential sources:

- Reddit
- X
- YouTube
- TikTok
- Instagram
- Hacker News
- Bluesky
- Truth Social
- Polymarket
- grounded web
- Xiaohongshu

Availability depends on credentials and local tools. Run `--diagnose` to see what is live in the current environment.

## Configuration

Primary environment variables:

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

Config loads from:

1. process env
2. `.claude/last30days.env` in the repo tree
3. `~/.config/last30days/.env`

## CLI

```bash
python3 scripts/last30days.py "codex vs claude code"
python3 scripts/last30days.py "anthropic odds" --emit=json
python3 scripts/last30days.py "claude code skills" --quick
python3 scripts/last30days.py "remotion animations for Claude Code" --deep
python3 scripts/last30days.py "ai coding agents" --search=reddit,x,grounding
python3 scripts/last30days.py --diagnose
```

Emit modes:

- `compact`
- `md`
- `json`
- `context`

Depth modes:

- `--quick`: low-latency first pass
- default: balanced retrieval and enrichment
- `--deep`: highest recall and heaviest enrichment

## Development

Core commands:

```bash
python3 scripts/last30days.py "test topic" --mock --emit=compact
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m py_compile $(rg --files scripts tests -g '*.py' -g '!scripts/lib/vendor/**')
bash scripts/sync.sh
```

`scripts/sync.sh` updates the installed skill copies under:

- `~/.claude/skills/last30days`
- `~/.agents/skills/last30days`
- `~/.codex/skills/last30days`

## Docs

Active docs:

- [How Search Works](/Users/js/projects/last30days-skill/docs/how-search-works.md)
- [Search Quality Eval](/Users/js/projects/last30days-skill/docs/search-quality-eval.md)
- [Changelog](/Users/js/projects/last30days-skill/CHANGELOG.md)

Archived materials under `docs/plans/` and `docs/comparison-results/` are historical reference, not the current product description.
