# last30days v3.0.0

`last30days` is a live recency-research skill for the last 30 days. It searches across social, market, and grounded web sources, fuses everything into one ranked pool, and renders evidence clusters instead of source buckets.

The current runtime is a hard-cut v3 pipeline:

1. Query planning (deterministic for comparisons, LLM-assisted for other intents)
2. Per-`(subquery, source)` retrieval with capability-based source routing
3. Normalization, within-source dedupe, and low-relevance pruning
4. Per-source engagement scoring and snippet extraction
5. Weighted reciprocal rank fusion
6. Single-score reranking with low-confidence demotion
7. Cluster formation and MMR representative selection
8. Cluster-first rendering with inline engagement, dates, and corroboration

## Runtime

Gemini `3.1` preview is the primary runtime:

- planner: `gemini-3.1-flash-lite-preview`
- rerank `quick` / `default`: `gemini-3.1-flash-lite-preview`
- rerank `deep`: `gemini-3.1-pro-preview`
- Google Search grounding: `gemini-3.1-flash-lite-preview`

OpenAI and xAI are still supported as fallback reasoning providers. X retrieval can use xAI or Bird cookie auth. Public web retrieval is grounded through Gemini.

### Query planning

Comparison queries with explicit separators (`vs`, `versus`, `/`, `difference between`) use deterministic entity decomposition. The raw entity names are preserved as-is in search queries -- no LLM rewriting. This prevents hallucination for niche proper nouns the LLM doesn't recognize.

Other intents use LLM-assisted planning with a deterministic fallback. If the LLM call fails, the error is logged to stderr and the plan notes record the failure type.

### Source routing

For `comparison` and `how_to` intents at `default` depth, sources are selected by capability matching (discussion, video, web, market, social) rather than a fixed editorial priority list. This lets fusion and reranking decide quality rather than hard-coded source ordering. `quick` mode still uses tight source budgets for latency.

### Engagement scoring

Each source has its own engagement formula:

- Reddit: score + comments + upvote_ratio + top-comment quality
- X: likes + reposts + replies + quotes
- YouTube: views + likes + comments
- TikTok/Instagram: views + likes + comments
- Hacker News: points + comments
- Bluesky: likes + reposts + replies + quotes
- Truth Social: likes + reposts + replies
- Polymarket: volume + liquidity

### Rendering

Compact output is cluster-first with inline engagement brackets (`[344pts, 119cmt]`), dates with confidence indicators, author/container context, corroboration from fused candidates (`Also on: X, HN`), top-comment excerpts, freshness warnings, and a source coverage footer. Internal score breakdowns and `fallback-local-score` sentinels are suppressed.

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

In OpenClaw, the gateway can also inject env from `~/.openclaw/.env` or `~/.openclaw/openclaw.json` before the skill runs.

## Skill surfaces

The repo now supports two skill wrappers on top of the same v3 engine:

- root [SKILL.md](/Users/js/projects/last30days-skill/SKILL.md): one-shot research for Claude Code, Codex, Gemini, and basic OpenClaw installs
- [variants/open/SKILL.md](/Users/js/projects/last30days-skill/variants/open/SKILL.md): persistent OpenClaw-style workflow with watchlists, briefings, and history

The OpenClaw variant restores the upstream `watch`, `briefing`, and `history` behavior on top of the v3 pipeline. It does not restore the removed Brave / Parallel / OpenRouter web stack. Public web retrieval stays on Gemini grounding.

## CLI

```bash
python3 scripts/last30days.py "codex vs claude code"
python3 scripts/last30days.py "anthropic odds" --emit=json
python3 scripts/last30days.py "claude code skills" --quick
python3 scripts/last30days.py "remotion animations for Claude Code" --deep
python3 scripts/last30days.py "ai coding agents" --search=reddit,x,grounding
python3 scripts/last30days.py "openclaw skills" --store
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

## OpenClaw

Official OpenClaw docs describe skills as AgentSkills-compatible folders loaded from workspace `<workspace>/skills`, then `~/.openclaw/skills`, then optional extra dirs via `skills.load.extraDirs` in `~/.openclaw/openclaw.json`. Relevant docs:

- [OpenClaw skills](https://docs.openclaw.ai/tools/skills)
- [OpenClaw skills config](https://docs.openclaw.ai/tools/skills-config)
- [OpenClaw CLI skills](https://docs.openclaw.ai/cli/skills)
- [ClawHub](https://docs.openclaw.ai/tools/clawhub)

Manual install:

```bash
git clone https://github.com/mvanhorn/last30days-skill.git ~/.openclaw/skills/last30days
cp ~/.openclaw/skills/last30days/variants/open/SKILL.md ~/.openclaw/skills/last30days/SKILL.md
```

Higher-precedence per-agent install:

```bash
git clone https://github.com/mvanhorn/last30days-skill.git ~/.openclaw/workspace/skills/last30days
cp ~/.openclaw/workspace/skills/last30days/variants/open/SKILL.md ~/.openclaw/workspace/skills/last30days/SKILL.md
```

If you want to keep the repo elsewhere, add its parent directory to `skills.load.extraDirs` in `~/.openclaw/openclaw.json`.

The OpenClaw wrapper exposes:

- one-shot research with `--store`
- `watch` via [scripts/watchlist.py](/Users/js/projects/last30days-skill/scripts/watchlist.py)
- `briefing` via [scripts/briefing.py](/Users/js/projects/last30days-skill/scripts/briefing.py)
- `history` via [scripts/store.py](/Users/js/projects/last30days-skill/scripts/store.py)

## Development

Core commands:

```bash
python3 scripts/last30days.py "test topic" --mock --emit=compact
uv run python -m pytest tests/ -v
python3 scripts/verify_v3.py --skip-eval
bash scripts/sync.sh
```

The test suite (187 tests) includes regression tests for the original `openclaw vs nanoclaw vs ironclaw` failure, adversarial planner tests (slash separators, "difference between" phrasing, trailing context, degenerate inputs), and unit tests for engagement scoring, render formatting, dedupe similarity, and rerank internals.

`scripts/sync.sh` updates the installed skill copies under:

- `~/.claude/skills/last30days`
- `~/.agents/skills/last30days`
- `~/.codex/skills/last30days`
- `~/.openclaw/skills/last30days`

## Docs

Active docs:

- [How Search Works](/Users/js/projects/last30days-skill/docs/how-search-works.md)
- [Search Quality Eval](/Users/js/projects/last30days-skill/docs/search-quality-eval.md)
- [Changelog](/Users/js/projects/last30days-skill/CHANGELOG.md)

Archived materials under `docs/plans/` and `docs/comparison-results/` are historical reference, not the current product description.
