---
name: last30days
version: "3.0.0"
description: "Persistent last-30-days research for OpenClaw: one-shot research, watchlists, briefings, and history."
argument-hint: 'last30 watch "competitors", last30 briefing, last30 history "AI video", last30 codex vs claude code'
allowed-tools: Bash, Read, Write, AskUserQuestion, WebSearch
homepage: https://github.com/mvanhorn/last30days-skill
repository: https://github.com/mvanhorn/last30days-skill
author: mvanhorn
license: MIT
user-invocable: true
metadata:
  openclaw:
    emoji: "📰"
    requires:
      optionalEnv:
        - GOOGLE_API_KEY
        - BRAVE_API_KEY
        - SERPER_API_KEY
        - SCRAPECREATORS_API_KEY
        - OPENAI_API_KEY
        - XAI_API_KEY
        - BSKY_HANDLE
        - BSKY_APP_PASSWORD
        - TRUTHSOCIAL_TOKEN
        - AUTH_TOKEN
        - CT0
      bins:
        - node
        - python3
    files:
      - "scripts/*"
      - "variants/open/*"
      - "variants/open/references/*"
    homepage: https://github.com/mvanhorn/last30days-skill
    tags:
      - research
      - watchlist
      - briefing
      - history
      - web-search
      - multi-source
      - analysis
---

# last30days v3.0.0 (Open Variant)

Use this wrapper when you want last30days to remember what it found.

It adds persistent workflows on top of normal one-shot research:

- one-shot research that can store findings
- watchlist topics
- briefings
- history queries

Keep the product story the same as the main skill:

- it works out of the box
- X cookies and `yt-dlp` are the best free upgrades
- ScrapeCreators is the biggest optional paid upgrade
- Brave and Serper are optional native web upgrades

## Setup: resolve the skill root

```bash
for dir in \
  "." \
  "${CLAUDE_PLUGIN_ROOT:-}" \
  "${GEMINI_EXTENSION_DIR:-}" \
  "$HOME/.openclaw/workspace/skills/last30days" \
  "$HOME/.openclaw/skills/last30days" \
  "$HOME/.claude/skills/last30days" \
  "$HOME/.agents/skills/last30days" \
  "$HOME/.codex/skills/last30days"; do
  [ -n "$dir" ] && [ -f "$dir/scripts/last30days.py" ] && SKILL_ROOT="$dir" && break
done

if [ -z "${SKILL_ROOT:-}" ]; then
  echo "ERROR: Could not find scripts/last30days.py" >&2
  exit 1
fi
```

Use `$SKILL_ROOT` for all scripts and reference files.

## Session context

At session start, read `${SKILL_ROOT}/variants/open/context.md`. Update it after meaningful watchlist, briefing, history, or one-shot interactions when you learn durable user preferences.

## Runtime expectations

- The research engine works out of the box with Reddit public threads, Hacker News, and Polymarket.
- `last30days setup` is still the recommended first upgrade path when available in the host environment.
- `BRAVE_API_KEY` enables Brave web search. `SERPER_API_KEY` is the native web fallback.
- Reasoning-provider keys are optional runtime upgrades for planning and reranking, not the first thing to ask users for.
- OpenClaw can supply env vars through `~/.openclaw/.env` or `~/.openclaw/openclaw.json`.
- `last30days` also reads process env, repo `.claude/last30days.env`, and `~/.config/last30days/.env`.
- This open variant uses the same Brave/Serper web retrieval path as the main skill.

## Command routing

Interpret the first word of the user request:

| First word | Mode | Reference |
| --- | --- | --- |
| `watch` | watchlist management | `${SKILL_ROOT}/variants/open/references/watchlist.md` |
| `briefing` | briefing generation | `${SKILL_ROOT}/variants/open/references/briefing.md` |
| `history` | stored research queries | `${SKILL_ROOT}/variants/open/references/history.md` |
| anything else | one-shot research | `${SKILL_ROOT}/variants/open/references/research.md` |

Read the matching reference file before acting.
