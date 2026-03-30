# One-Shot Research Mode

Research recent discussion across live social, market, and grounded web sources, then turn it into a guided OpenClaw answer.

## Parse user intent

Before calling tools, parse:

1. `TOPIC`
2. `TARGET_TOOL` if one is named
3. `QUERY_TYPE`: `PROMPTING`, `RECOMMENDATIONS`, `NEWS`, `COMPARISON`, or `GENERAL`

Display this pre-flight block before the first tool call:

```text
I'll research {TOPIC} across recent social, market, and web sources from the last 30 days.

Parsed intent:
- TOPIC = {TOPIC}
- TARGET_TOOL = {TARGET_TOOL or "unknown"}
- QUERY_TYPE = {QUERY_TYPE}

Research typically takes 2-8 minutes. Starting now.
```

If `TARGET_TOOL` is unknown for a prompt-oriented request, do not ask yet. Research first, then ask once with `AskUserQuestion` after showing findings.

## Step 0.5: Resolve X handle

If the topic could have its own X account, do one quick `WebSearch`:

```text
WebSearch("{TOPIC} X twitter handle site:x.com")
```

If you find a verified handle, pass `--x-handle={handle}` without `@`.

## Run the CLI

Default one-shot runs in the OpenClaw variant should persist into the research store:

```bash
python3 "${SKILL_ROOT}/scripts/last30days.py" $ARGUMENTS --emit=compact --store
```

Use these variants when the user asked for them:

- `--quick` for a fast first pass
- `--deep` for maximum recall
- `--emit=json` only for machine-readable output
- `--search=` only when the user explicitly restricted sources

## Web supplementation

Do not guess whether native web is available. Detect it explicitly:

1. Run `python3 "${SKILL_ROOT}/scripts/last30days.py" --diagnose` before the main command when you need to decide on fallback up front.
2. Treat native grounded web as available only when `native_web_backend` is not `null` and `"grounding"` appears in `available_sources`.
3. If you already ran the main command, the CLI banner and completion line also tell you whether `Web` was active.

If native grounded web retrieval is missing by those signals, use the host `WebSearch` tool after the CLI run and fold those results into the synthesis.

Recommended queries:

- `PROMPTING`: `{TOPIC} prompts examples`, `{TOPIC} techniques tips`
- `RECOMMENDATIONS`: `best {TOPIC}`, `{TOPIC} examples`
- `NEWS`: `{TOPIC} news`, `{TOPIC} update`
- `COMPARISON`: `{TOPIC} comparison`
- `GENERAL`: `{TOPIC} discussion`, `{TOPIC} 2026`

## Display results

Do not return the raw compact report unframed. Turn the research into a guided OpenClaw answer with:

1. `What I learned`
2. `Stats`
3. A short invitation with 2-3 concrete follow-up suggestions based on the actual findings

For comparison requests, include a quick verdict and a short head-to-head.

For prompt-oriented requests:

1. explain the research-backed patterns briefly
2. if needed, ask once which tool the prompt is for
3. write one copy-paste-ready prompt that matches the format the research says works

## Follow-up behavior

After the first answer, stay in expert mode for this topic. Use the stored findings and the just-completed research for follow-ups. Only run new research when the user changes topics.
