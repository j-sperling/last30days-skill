# Search Quality Evaluation

`scripts/evaluate_search_quality.py` compares two revisions of the v3 pipeline on a fixed topic set and writes a compact local benchmark bundle.

It is a local engineering tool, not part of the user-facing runtime.

## What it measures

For each topic, the evaluator compares `ranked_candidates` between a baseline revision and a candidate revision.

Outputs include:

- `Precision@5`
- `nDCG@5`
- source-coverage recall
- overall Jaccard overlap
- retention vs baseline
- per-source overlap
- optional failure summaries when a topic run breaks

Judging is done with Gemini when a Google key is available.

## Default topic set

The built-in topics are:

- `nano banana pro prompting`
- `codex vs claude code`
- `anthropic odds`
- `kanye west`
- `remotion animations for Claude Code`

## Usage

Balanced live comparison:

```bash
python3 scripts/evaluate_search_quality.py \
  --baseline=origin/main \
  --candidate=HEAD \
  --output-dir=/tmp/last30days-eval
```

Quick mock smoke:

```bash
python3 scripts/evaluate_search_quality.py \
  --baseline=HEAD \
  --candidate=HEAD \
  --mock \
  --quick \
  --timeout=60 \
  --output-dir=/tmp/last30days-eval-smoke
```

## Useful flags

- `--baseline`
- `--candidate`
- `--search`
- `--output-dir`
- `--judge-model`
- `--timeout`
- `--limit`
- `--mock`
- `--quick`
- `--topics-file`

## Output files

The evaluator writes:

- `summary.md`
- `metrics.json`
- `judgments/*.json`

`metrics.json` contains both per-topic metrics and any recorded failures.

## Auth and environment

The evaluator shells out to `scripts/last30days.py` in separate worktrees when needed. It passes the normal runtime credentials through a clean env:

- `GOOGLE_API_KEY`
- `OPENAI_API_KEY`
- `XAI_API_KEY`
- `SCRAPECREATORS_API_KEY`
- source-specific optional credentials

The Google judge key can come from:

- `GOOGLE_API_KEY`
- `GEMINI_API_KEY`
- `GOOGLE_GENAI_API_KEY`

## Notes

- Source coverage is based on fused v3 candidate provenance, not just the primary source label.
- Candidate dates for judging come from the best dated `source_item` attached to each fused candidate.
- Jaccard and retention are regression guards. They are useful for change detection, not for measuring absolute truth.
