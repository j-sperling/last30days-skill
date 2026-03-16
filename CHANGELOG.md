# Changelog

This project follows semantic versioning. The v3 line is a hard-cut rewrite of the runtime and docs surface.

## [3.0.0] - 2026-03-16

### Changed

- replaced the source-first pipeline with a planner-driven ranked evidence pipeline
- replaced generic web backends with Gemini Google Search grounding
- replaced heuristic score stacking with local signals, weighted RRF, and a single-score reranker
- replaced loose cross-source links with explicit clusters and representative selection
- switched the default documentation and skill surface to the v3 report model
- restored the persistent OpenClaw wrapper on top of the v3 engine, including `watch`, `briefing`, `history`, and one-shot `--store` persistence

### Removed

- legacy query typing in `query_type.py`
- legacy score policy in `score.py`
- cache and model-discovery layers that were no longer part of the runtime
- deprecated web backends and old source adapters including Brave, OpenRouter, Parallel, and the old OpenAI Reddit path
- the old source-first output model

## Pre-v3 history

Pre-v3 releases are still available in git history, but they no longer describe the current architecture and are intentionally not carried forward in the active documentation set.
