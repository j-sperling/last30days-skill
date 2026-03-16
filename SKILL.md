---
name: last30days
version: "3.0.0"
description: "Cluster-first last-30-days research across social, market, and grounded web sources."
argument-hint: "last30days codex vs claude code"
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
      - recency
      - grounding
      - gemini
      - multi-source
      - analysis
---

# last30days v3.0.0

Use `last30days` when the user wants recent, cross-source evidence from the last 30 days.

The runtime is a single v3 pipeline:

1. plan the query
2. retrieve per `(subquery, source)`
3. normalize and dedupe
4. extract best snippets
5. fuse with weighted RRF
6. rerank with one relevance score
7. cluster evidence
8. render ranked clusters

## Default command

```bash
python3 "${SKILL_ROOT}/scripts/last30days.py" "$ARGUMENTS" --emit=compact
```

## Useful commands

```bash
python3 "${SKILL_ROOT}/scripts/last30days.py" "$ARGUMENTS" --emit=json
python3 "${SKILL_ROOT}/scripts/last30days.py" "$ARGUMENTS" --quick
python3 "${SKILL_ROOT}/scripts/last30days.py" "$ARGUMENTS" --deep
python3 "${SKILL_ROOT}/scripts/last30days.py" "$ARGUMENTS" --search=reddit,x,grounding
python3 "${SKILL_ROOT}/scripts/last30days.py" --diagnose
```

## Runtime expectations

- `GOOGLE_API_KEY` is the primary credential. It enables Gemini planning, reranking, and Google Search grounding.
- Gemini `3.1` preview is the required Gemini runtime.
- `SCRAPECREATORS_API_KEY` enables Reddit, TikTok, and Instagram.
- `XAI_API_KEY` enables xAI reasoning and X search.
- `AUTH_TOKEN` plus `CT0` enables Bird-backed X search.
- `yt-dlp` enables YouTube.

## Output model

- `compact` and `md`: cluster-first markdown
- `json`: full v3 report
- `context`: short synthesis-oriented context

Important report fields:

- `provider_runtime`
- `query_plan`
- `ranked_candidates`
- `clusters`
- `items_by_source`
- `errors_by_source`

## Usage guidance for agents

- Prefer `--quick` for fast iteration.
- Prefer default mode when the user wants a balanced answer.
- Prefer `--deep` only when the user explicitly wants maximum recall or the topic is complex enough to justify extra latency.
- Prefer `--emit=json` when downstream code or evaluation will consume the result.
- Use `--search=` only when the user explicitly wants source restrictions.
- Do not describe the old source-first layout or the removed Brave / OpenRouter / Parallel web stack. Those are not part of v3.
