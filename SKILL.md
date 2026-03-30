---
name: last30days
version: "3.0.0"
description: "Research any topic from the last 30 days across Reddit, X, YouTube, TikTok, Instagram, Hacker News, Bluesky, Truth Social, Polymarket, and the web."
argument-hint: "last30days codex vs claude code"
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
        - SCRAPECREATORS_API_KEY
        - BRAVE_API_KEY
        - SERPER_API_KEY
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
    primaryEnv: GOOGLE_API_KEY
    files:
      - "scripts/*"
    homepage: https://github.com/mvanhorn/last30days-skill
    tags:
      - research
      - deep-research
      - reddit
      - x
      - twitter
      - youtube
      - tiktok
      - instagram
      - hackernews
      - polymarket
      - bluesky
      - truthsocial
      - trends
      - recency
      - news
      - citations
      - multi-source
      - social-media
      - web-search
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

## Interactive UX contract

Before calling any tools, parse the user's request into:

- `TOPIC`
- `TARGET_TOOL` if they named one
- `QUERY_TYPE`: `PROMPTING`, `RECOMMENDATIONS`, `NEWS`, `COMPARISON`, or `GENERAL`

Always show the user a short pre-flight message before the first tool call:

```text
I'll research {TOPIC} across recent social, market, and web sources from the last 30 days -- synthesizing what people are actually saying right now.

Research typically takes 2-8 minutes. Starting now.
```

This pre-flight block is required. It confirms you understood the request and sets expectations.

For prompt-oriented requests, do not ask about `TARGET_TOOL` before research. If the tool is still unknown after research, use `AskUserQuestion` once after presenting findings, then write one copy-paste-ready prompt that matches what the research says works for that tool.

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

## Default command

```bash
python3 "${SKILL_ROOT}/scripts/last30days.py" $ARGUMENTS --emit=compact
```

If the user wants persistent storage, add `--store`. If they want machine-readable output, use `--emit=json`.

## Useful commands

```bash
python3 "${SKILL_ROOT}/scripts/last30days.py" $ARGUMENTS --emit=json
python3 "${SKILL_ROOT}/scripts/last30days.py" $ARGUMENTS --quick
python3 "${SKILL_ROOT}/scripts/last30days.py" $ARGUMENTS --deep
python3 "${SKILL_ROOT}/scripts/last30days.py" $ARGUMENTS --search=reddit,x,grounding
python3 "${SKILL_ROOT}/scripts/last30days.py" $ARGUMENTS --store
python3 "${SKILL_ROOT}/scripts/last30days.py" --diagnose
```

## Do I need API keys?

**You do NOT need API keys to use last30days.** It works out of the box with Reddit (public threads), Hacker News, Polymarket, and YouTube. Browser cookies for X/Twitter are detected automatically -- just log into x.com in Firefox or Safari.

**Source unlock progression (most steps are free):**
- **Zero config (40% quality):** Reddit (public threads), HN, Polymarket -- works immediately
- **+ X cookies (60%):** Log into x.com in Firefox or Safari. Cookies are detected automatically on next run. Same access as an API key, no signup required.
- **+ yt-dlp (80%):** `brew install yt-dlp` -- free, open source. Enables YouTube search and transcript extraction.
- **+ ScrapeCreators (100%):** The single most impactful upgrade. Unlocks Reddit with full comment threads (the highest-value research content -- real user opinions with upvote signals), plus TikTok and Instagram. 100 free API calls, no credit card -- scrapecreators.com

last30days has no affiliation with any API provider -- no referrals, no kickbacks.

## Runtime details

- Planning and reranking fall back gracefully: Gemini -> OpenAI -> xAI -> deterministic/local. No reasoning provider key needed for basic operation.
- `BRAVE_API_KEY` or `EXA_API_KEY` or `SERPER_API_KEY` enables native web search (optional -- the host's WebSearch tool is used as fallback).
- Web retrieval stays within dated results. Undated web hits are dropped.
- For OpenClaw-specific watchlist, briefing, and history workflows, use `variants/open/SKILL.md`.

## Web fallback for plugin hosts

Do not guess whether native web is available. Detect it explicitly:

1. Run `python3 "${SKILL_ROOT}/scripts/last30days.py" --diagnose` when you need to decide on web fallback before the main command.
2. Treat native grounded web as available only when `native_web_backend` is not `null` and `"grounding"` appears in `available_sources`.
3. If you already ran the main command, the CLI banner and completion line also tell you whether `Web` was active.

If native grounded web retrieval is missing by those signals, supplement the CLI output with the host `WebSearch` tool. Use the user's exact terminology, avoid duplicate platform coverage already handled by the CLI, and fold the web findings into the final synthesis instead of dumping raw search results.

Recommended fallback queries:

- `PROMPTING`: `{TOPIC} prompts examples`, `{TOPIC} techniques tips`
- `RECOMMENDATIONS`: `best {TOPIC}`, `{TOPIC} examples`
- `NEWS`: `{TOPIC} news`, `{TOPIC} update`
- `COMPARISON`: `{TOPIC} comparison`
- `GENERAL`: `{TOPIC} discussion`, `{TOPIC} 2026`

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

## X handle resolution

If the topic could have its own X/Twitter account (people, brands, products, companies), do a quick WebSearch for their handle:
```
WebSearch("{TOPIC} X twitter handle site:x.com")
```
If you find a verified handle, pass `--x-handle={handle}` (without @). This searches their posts directly, finding content they posted that doesn't mention their own name. Skip this for generic concepts ("best headphones 2026", "how to use Docker").

## Display contract

After research finishes, synthesize into a user-facing answer. Do not just paste the raw compact output back to the user.

Always include:

1. `What I learned`
2. `Stats` (the tree-format stats block from the compact output)
3. An invitation adapted to the QUERY_TYPE, with 2-3 specific suggestions drawn from the actual findings

**Invitation templates by QUERY_TYPE:**

**PROMPTING:**
> I'm now an expert on {TOPIC} for {TARGET_TOOL}. What do you want to make? For example:
> - [specific idea based on popular technique from research]
> - [specific idea based on trending style/approach from research]
> - [specific idea riffing on what people are actually creating]
>
> Just describe your vision and I'll write a prompt you can paste straight into {TARGET_TOOL}.

**RECOMMENDATIONS:**
> I'm now an expert on {TOPIC}. Want me to go deeper? For example:
> - [Compare specific item A vs item B from the results]
> - [Explain why item C is trending right now]
> - [Help you get started with item D]

**NEWS:**
> I'm now an expert on {TOPIC}. Some things you could ask:
> - [Specific follow-up question about the biggest story]
> - [Question about implications of a key development]
> - [Question about what might happen next based on current trajectory]

**COMPARISON:**
> I've compared {TOPIC_A} vs {TOPIC_B} using the latest community data. Some things you could ask:
> - [Deep dive into {TOPIC_A} alone]
> - [Deep dive into {TOPIC_B} alone]
> - [Focus on a specific dimension from the comparison table]

**GENERAL:**
> I'm now an expert on {TOPIC}. Some things I can help with:
> - [Specific question based on the most discussed aspect]
> - [Specific creative/practical application of what you learned]
> - [Deeper dive into a pattern or debate from the research]

Every invitation MUST reference real things from the research -- show the user you absorbed the content.

**WebSearch citation note:** The stats block's source names on the Web line satisfy the WebSearch tool's citation mandate. Do NOT append a separate "Sources:" section at the end of your response.

For prompt-oriented requests:

- first explain the research-backed patterns briefly
- then write one prompt, not a prompt pack
- match the format the research recommends for the target tool
- if the target tool is still unknown, ask once after the findings, then write the prompt

## Synthesis guidance

### First: synthesize, don't summarize

Extract key facts from the output first, then synthesize across sources. Lead with patterns that appear across multiple clusters. Present a unified narrative, not a source-by-source summary.

### Ground in actual research, not pre-existing knowledge

Use exact product/tool names, specific quotes, and what sources actually say. If research mentions "ClawdBot" and "@clawdbot", that is a different product than "Claude Code" -- read what the research actually says.

**Anti-pattern to avoid:**
- BAD: User asks "best Claude Code skills" and you respond with generic advice: "Skills are powerful. Keep them under 500 lines."
- GOOD: You respond with specifics from the research: "Most mentioned: /commit (5 mentions), remotion skill (4x), git-worktree (3x). The Remotion announcement got 16K likes on X per @thedorbrothers."

### Source weighting (highest to lowest signal)

1. **Cross-cluster corroboration** -- same evidence across multiple sources is the strongest signal. Lead with it.
2. **Reddit top comments** -- often the wittiest, most insightful take. Quote directly when upvotes are high.
3. **YouTube transcript highlights** -- pre-extracted key moments. Quote and attribute to channel name.
4. **X/Twitter @handles** -- real-time community signal. Quote with engagement context.
5. **Polymarket odds** -- real money on outcomes cuts through opinion. Include specific odds AND movement.
6. **TikTok/Instagram** -- viral/creator signal. Cite @creators with views/likes.
7. **Hacker News** -- technical community perspective. Cite as "per HN."
8. **Web (Brave/Serper)** -- cite only when social sources don't cover a fact.

### Polymarket interpretation

When Polymarket returns relevant markets:
1. Prefer structural/long-term markets over near-term deadlines (championship odds > regular season, IPO > incremental update)
2. Call out the specific outcome's odds and movement, not just that a market exists
3. Weave odds into the narrative as supporting evidence, don't isolate them
4. When multiple relevant markets exist, highlight 3-5 ordered by importance

Domain importance ranking:
- **Sports:** Championship/tournament > conference title > regular season > weekly matchup
- **Geopolitics:** Regime change/structural > near-term strike deadlines > sanctions
- **Tech/Business:** IPO, major product launch > incremental updates
- **Elections:** Presidency > primary > individual state

### Citation rules

Cite the single strongest source per point in short format: "per @handle" or "per r/subreddit". Use the priority order from source weighting above. The tool's value is surfacing what PEOPLE are saying, not what journalists wrote.

**Anti-patterns:**
- Do NOT chain citations: "per @x, @y, @z" is too many -- cite the single strongest source
- Do NOT include engagement metrics in citations (save for the stats block)
- Never paste raw URLs in the synthesis narrative
- Lead with people, not publications: when both a web article and an X post cover the same fact, cite the X post
- Parse @handles from the research output and include the highest-engagement ones in your synthesis

### Comparison queries

For "X vs Y" queries, structure output as:

```
## Quick Verdict
[1-2 sentences: which one the community prefers and why, with source counts]

## [Entity A]
**Community Sentiment:** [Positive/Mixed/Negative] (N mentions across sources)
**Strengths:** [with source attribution]
**Weaknesses:** [with source attribution]

## [Entity B]
[Same structure]

## Head-to-Head
| Dimension | Entity A | Entity B |
|-----------|----------|----------|
| [Key dim] | [position] | [position] |

## Bottom Line
Choose A if... Choose B if... (based on community data)
```

### Recommendation queries

When users ask "best X" or "top X", extract SPECIFIC NAMES:

```
Most mentioned:
[Name] -- Nx mentions
  Use case: [what it does / why people recommend it]
  Sources: @handle1, r/subreddit, [YouTube channel]

[Name] -- Nx mentions
  Use case: [what it does / why people recommend it]
  Sources: @handle2, r/subreddit2

Notable mentions: [others with 1-2 mentions]
```

### Prompting queries

When the user is asking for prompts or techniques for a specific tool:

1. research first
2. extract the concrete prompt patterns that recur across the sources
3. explain those patterns briefly
4. write one copy-paste-ready prompt for the requested tool

If the research indicates a specific format such as JSON, structured fields, or multi-part prompting, use that format in the final prompt instead of plain prose.

**Quality checklist (run before delivering a prompt):**
- [ ] FORMAT MATCHES RESEARCH -- if research said JSON/structured/etc, prompt IS that format
- [ ] Directly addresses what the user said they want to create
- [ ] Uses specific patterns/keywords discovered in research
- [ ] Ready to paste with zero edits (or minimal [PLACEHOLDERS] clearly marked)
- [ ] Appropriate length and style for TARGET_TOOL

### Edge cases

- **Empty results from a source:** State what is missing. ("No Reddit discussion found for this topic.") Do not fill the gap with training data.
- **Sources contradict each other:** Present both sides with attribution. ("Reddit r/fitness is bullish on X, while @DrExpert on X warns about Y.")
- **All results are low-engagement or off-topic:** Acknowledge uncertainty. ("Limited recent discussion found -- these findings should be treated as preliminary.")

### Follow-up conversations

After research completes, treat yourself as an expert on this topic. Answer follow-ups from the research findings. Cite the specific threads, posts, and channels you found. Only run new research if the user asks about a DIFFERENT topic.

### Query type classification

Classify each request to choose the right follow-up invitation:
- "best X" or "top X" -> RECOMMENDATIONS
- "X prompts" or "write a prompt for" -> PROMPTING
- "X news" or "what happened with" -> NEWS
- "X vs Y" -> COMPARISON
- everything else -> GENERAL

### Follow-up invitation templates

After presenting findings and stats, close with a query-type-adapted invitation. Include 2-3 specific suggestions drawn from the actual research findings.

**COMPARISON:**
> I've compared {A} vs {B} using the latest community data. You could:
> - Deep-dive into {A} alone with /last30days {A}
> - Deep-dive into {B} alone with /last30days {B}
> - Focus on a specific dimension from the comparison table

**RECOMMENDATIONS:**
> I'm now an expert on {TOPIC}. Want me to go deeper?
> - Compare specific item A vs item B from the results
> - Explain why item C is trending right now
> - Help you get started with item D

**NEWS:**
> I'm now an expert on {TOPIC}. Some things you could ask:
> - [Follow-up about the biggest story]
> - [Implications of a key development]
> - [What might happen next based on current trajectory]

**PROMPTING:**
> I'm now an expert on {TOPIC} for {TARGET_TOOL}. What do you want to make?
> - [Specific technique from research]
> - [Trending approach from research]
> - [Creative application from research]
> Just describe your vision and I'll write a prompt you can paste in.

**GENERAL:**
> I'm now an expert on {TOPIC}. Some things I can help with:
> - [Question about the most-discussed aspect]
> - [Practical application of what was learned]
> - [Deeper dive into a pattern or debate from the research]

### Stats footer

The CLI output includes a `## Stats` section with per-source counts and top voices. In your synthesis, present these as a summary line:

> Based on: {N} Reddit threads ({sum} upvotes) + {N} X posts ({sum} likes) + {N} YouTube videos ({sum} views) + ...
> Top voices: @handle1, r/subreddit1, ChannelName

Omit any source with 0 results. Include engagement totals only for sources that have them.

## Security and permissions

**What this skill does:**
- Sends search queries to ScrapeCreators API for Reddit, TikTok, Instagram search
- Sends search queries via xAI API or Bird client for X search
- Sends search queries to Algolia HN Search API (free, no auth)
- Sends search queries to Polymarket Gamma API (free, no auth)
- Runs yt-dlp locally for YouTube search and transcript extraction (no API key)
- Sends search queries to Brave Search API or Serper for web search (optional)
- Uses Gemini, OpenAI, or xAI for LLM planning and reranking
- Stores findings in local SQLite database (--store mode only)

**What this skill does NOT do:**
- Does not post, like, or modify content on any platform
- Does not access your personal accounts on any platform
- Does not share API keys between providers
- Does not log or cache API keys in output files
