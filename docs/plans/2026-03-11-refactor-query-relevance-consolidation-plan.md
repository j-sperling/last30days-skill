# Search Pipeline: Query & Relevance Consolidation

## Strategy: Two-phase delivery

**Phase 1 — Upstream PR** (`refactor/query-relevance-consolidation` -> `mvanhorn/last30days-skill:main`)
Pure refactors and bug fixes anyone would want. No behavior changes.

**Phase 2 — Fork-only** (`feat/search-quality` on `j-sperling/last30days-skill`)
Opinionated behavior changes: computed relevance scores, platform-specific query optimization, post-retrieval filtering.

---

## Phase 1: Upstream PR (refactors + bug fixes)

### Step 1: New `query.py` — shared query utilities
- Consolidate 7 duplicated `_extract_core_subject()` (bird_x, reddit, youtube_yt, tiktok, instagram, bluesky, scrapecreators_x) into one parameterized function
- `extract_core_subject(topic, noise=None, max_words=None, strip_suffixes=False)` — platform modules pass their own noise set and options to preserve current behavior
- Shared `PREFIXES` list (identical across all 7), shared `NOISE_WORDS` base set
- Each platform imports `extract_core_subject` and calls with its own overrides (e.g. bird_x passes `max_words=5, strip_suffixes=True`; youtube keeps tips/tricks/tutorial in its noise exclusion)
- Fix reddit.py prefix-loop missing `break` (apply all matching prefixes vs only first)
- Skip polymarket.py (too different — handles "last N days", preserves title case)
- Tests: `tests/test_query.py`

### Step 2: New `relevance.py` — shared relevance scoring
- Consolidate `_tokenize`, `_compute_relevance`, `STOPWORDS`, `SYNONYMS` from youtube_yt/tiktok/instagram
- `token_overlap_relevance(query, text, hashtags=None) -> float` — zero-dep, superset of all three implementations (hashtag substring matching from tiktok/instagram, synonym expansion from youtube)
- Unified `SYNONYMS` dict (youtube superset: includes svelte/vue entries missing from tiktok/instagram)
- Tests: `tests/test_relevance.py` (migrate from `test_youtube_relevance.py` + new hashtag tests)

### Step 6: urllib fallback for TikTok/Instagram (independent bug fix)
- `tiktok.py`: add `http.get()`/`http.post()` fallback when `_requests is None`
- `instagram.py`: same pattern
- Copies pattern from reddit.py's existing fallback

### Step 3: Integrate `query.py` into per-source modules (pure refactor)
- `bird_x.py`: replace lines 52-106 with import, call `extract_core_subject(topic, max_words=5, strip_suffixes=True, noise=BIRD_NOISE)`
- `reddit.py`: replace `NOISE_WORDS` + `_extract_core_subject` with query import; `expand_reddit_queries` imports from query.py too
- `youtube_yt.py`: replace `_extract_core_subject` with import, pass youtube-specific noise set (keeps tips/tricks/tutorial/guide/review)
- `tiktok.py`, `instagram.py`, `bluesky.py`: same replacement with their noise sets
- Update tests: 12+ test methods across 6 test files reference `module._extract_core_subject()` — either re-export from original modules or update test imports

### Step 8: Deduplicate relevance code in youtube/tiktok/instagram (pure refactor)
- `youtube_yt.py`: remove `STOPWORDS`, `SYNONYMS`, `_tokenize`, `_compute_relevance`; import from `relevance.py`
- `tiktok.py`: same
- `instagram.py`: same
- Update tests: `test_youtube_relevance.py`, `test_tiktok.py`, `test_instagram_sc.py`, `test_scrapecreators_x.py` reference `module._tokenize`/`module._compute_relevance` — re-export or update imports

### Commit order: 1 → 2 → 6 → 3 → 8

---

## Phase 2: Fork-only (behavior changes)

### Step 4: Replace hardcoded relevance with computed scores
- `bird_x.py:471` — `"relevance": 0.7` → `token_overlap_relevance(core_topic, text)`
- `reddit.py:223` — `"relevance": 0.7` → `token_overlap_relevance(core, title + " " + selftext)`
- `hackernews.py:139-141` — blend: `0.6 * rank_score + 0.4 * token_overlap`

### Step 5: Platform-specific query optimization
- `detect_query_type(topic)` — heuristic classifier (product/concept/opinion/how_to/comparison), added here not Phase 1
- `extract_compound_terms(topic)` — detect hyphenated/title-case terms, return quoted
- `bird_x.py`: OR-group construction for multi-concept queries, OR-based retry before word-dropping fallback
- `reddit.py`: conditional opinion/review suffix only for product/opinion queries (uses `detect_query_type`)
- `hackernews.py`: add `numericFilters: points>5`, `restrictSearchableAttributes=title`, use `extract_core_subject()` instead of raw topic
- `youtube_yt.py`: add `--dateafter YYYYMMDD` (from_date already in signature)

### Step 7: Post-retrieval relevance filtering in orchestrator
- `last30days.py` (after dedup): filter items with `relevance < 0.3` per source (only when list has >3 items)
- Extend fallback guarantee to all sources: keep top 3 by relevance if all filtered
- `rerank_with_embeddings()` — optional, env-var gated (`OPENAI_API_KEY` or `GOOGLE_API_KEY`), uses existing `http.py`, graceful fallback to token overlap

### Commit order: 4 → 5 → 7

---

## Verify

```bash
cd ~/projects/last30days-skill && python3 -m unittest discover -s tests -v
```
