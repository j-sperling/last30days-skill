---
name: last30days
version: "3.0.0"
description: "Cluster-first last-30-days research across social, market, and grounded web sources. Gemini 3.1 preview powers planning, reranking, and Google Search grounding."
argument-hint: 'last30days claude code skills, last30days codex vs claude code'
allowed-tools: Bash, Read, Write, WebSearch
homepage: https://github.com/mvanhorn/last30days-skill
repository: https://github.com/mvanhorn/last30days-skill
author: mvanhorn
license: MIT
user-invocable: true
metadata:
  openclaw:
    emoji: "📰"
    requires:
      env:
        - GOOGLE_API_KEY
      optionalEnv:
        - SCRAPECREATORS_API_KEY
        - OPENAI_API_KEY
        - XAI_API_KEY
        - BSKY_HANDLE
        - BSKY_APP_PASSWORD
        - TRUTHSOCIAL_TOKEN
        - AUTH_TOKEN
        - CT0
      bins:
        - python3
    primaryEnv: GOOGLE_API_KEY
    files:
      - "scripts/*"
    homepage: https://github.com/mvanhorn/last30days-skill
    tags:
      - research
      - deep-research
      - recency
      - grounding
      - gemini
      - social-media
      - multi-source
      - analysis
---

# last30days v3.0.0

`last30days` is a hard-cut rewrite around one ranked evidence pipeline:

1. Gemini `3.1` preview plans the query.
2. Each `(subquery, source)` stream retrieves independently.
3. Long items are reduced to best-match snippets.
4. Weighted RRF fuses all streams into one candidate pool.
5. A single-score reranker orders the shortlist.
6. Results render as evidence clusters, not source buckets.

## Default command

```bash
python3 "${SKILL_ROOT}/scripts/last30days.py" "$ARGUMENTS" --emit=compact
```

## Useful flags

```bash
python3 "${SKILL_ROOT}/scripts/last30days.py" "$ARGUMENTS" --emit=json
python3 "${SKILL_ROOT}/scripts/last30days.py" "$ARGUMENTS" --quick
python3 "${SKILL_ROOT}/scripts/last30days.py" "$ARGUMENTS" --deep
python3 "${SKILL_ROOT}/scripts/last30days.py" "$ARGUMENTS" --search=reddit,x,grounding
python3 "${SKILL_ROOT}/scripts/last30days.py" "$ARGUMENTS" --diagnose
```

## Runtime expectations

- Gemini `3.1` preview is the required Gemini runtime for planner, rerank, and grounding.
- `GOOGLE_API_KEY` enables Gemini planning, reranking, and Google Search grounding.
- `SCRAPECREATORS_API_KEY` enables Reddit, TikTok, and Instagram.
- `XAI_API_KEY` or Bird cookies enable X search.
- `yt-dlp` enables YouTube.

## Output model

- `compact` and `md` emit cluster-first markdown.
- `json` emits the v3 report:
  - `provider_runtime`
  - `query_plan`
  - `ranked_candidates`
  - `clusters`
  - `items_by_source`
  - `errors_by_source`
- `context` emits a short synthesis-oriented context view.

## Notes for agents

- Prefer `--quick` for iterative exploration.
- Prefer `--emit=json` when another tool or evaluator will consume the output.
- Use `--search=` when the user explicitly wants source restrictions.
- Do not refer to Brave, Parallel, OpenRouter, or the old source-first compact layout. Those were removed in `v3.0.0`.
