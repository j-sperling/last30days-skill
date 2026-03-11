"""Shared query utilities for /last30days search modules.

Consolidates duplicated _extract_core_subject() logic from bird_x, reddit,
youtube_yt, tiktok, instagram, bluesky, and scrapecreators_x into one
parameterized function. Each platform calls with its own overrides.
"""

import re
from typing import FrozenSet, List, Optional, Set

# Common multi-word prefixes stripped from all queries (identical across modules)
PREFIXES = [
    'what are the best', 'what is the best', 'what are the latest',
    'what are people saying about', 'what do people think about',
    'how do i use', 'how to use', 'how to',
    'what are', 'what is', 'tips for', 'best practices for',
]

# Multi-word suffixes (used by bird_x)
SUFFIXES = [
    'best practices', 'use cases', 'prompt techniques',
    'prompting techniques', 'prompting tips',
]

# Base noise words shared across most modules
NOISE_WORDS = frozenset({
    # Articles/prepositions/conjunctions
    'a', 'an', 'the', 'is', 'are', 'was', 'were', 'and', 'or',
    'of', 'in', 'on', 'for', 'with', 'about', 'to',
    # Question words
    'how', 'what', 'which', 'who', 'why', 'when', 'where',
    'does', 'should', 'could', 'would',
    # Research/meta descriptors
    'best', 'top', 'good', 'great', 'awesome', 'killer',
    'latest', 'new', 'news', 'update', 'updates',
    'trendiest', 'trending', 'hottest', 'hot', 'popular', 'viral',
    'practices', 'features', 'guide', 'tutorial',
    'recommendations', 'advice', 'review', 'reviews',
    'usecases', 'examples', 'comparison', 'versus', 'vs',
    'plugin', 'plugins', 'skill', 'skills', 'tool', 'tools',
    # Prompting meta words
    'prompt', 'prompts', 'prompting', 'techniques', 'tips',
    'tricks', 'methods', 'strategies', 'approaches',
    # Action words
    'using', 'uses', 'use',
    # Misc filler
    'people', 'saying', 'think', 'said', 'lately',
})


def extract_core_subject(
    topic: str,
    *,
    noise: Optional[FrozenSet[str]] = None,
    max_words: Optional[int] = None,
    strip_suffixes: bool = False,
) -> str:
    """Extract core subject from a verbose search query.

    Strips common question/meta prefixes and noise words to produce a
    compact search-friendly query. Platforms customize via parameters.

    Args:
        topic: Raw user query
        noise: Override noise word set (default: NOISE_WORDS)
        max_words: Cap result to N words (default: no cap)
        strip_suffixes: Also strip trailing multi-word suffixes (bird_x uses this)

    Returns:
        Cleaned query string
    """
    text = topic.lower().strip()
    if not text:
        return text

    # Phase 1: Strip multi-word prefixes (longest first, stop after first match)
    for p in PREFIXES:
        if text.startswith(p + ' '):
            text = text[len(p):].strip()
            break

    # Phase 2: Strip multi-word suffixes (opt-in)
    if strip_suffixes:
        for s in SUFFIXES:
            if text.endswith(' ' + s):
                text = text[:-len(s)].strip()
                break

    # Phase 3: Filter individual noise words
    noise_set = noise if noise is not None else NOISE_WORDS
    words = text.split()
    filtered = [w for w in words if w not in noise_set]

    # Apply word cap if requested
    if max_words is not None and filtered:
        filtered = filtered[:max_words]

    result = ' '.join(filtered) if filtered else text
    return result.rstrip('?!.') if not max_words else (result or topic.lower().strip())


# ---- Query type detection (heuristic, no LLM) ----

_OPINION_SIGNALS = frozenset({
    'worth', 'thoughts', 'opinion', 'opinions', 'review', 'reviews',
    'recommend', 'recommendation', 'recommendations', 'should',
    'anyone', 'anybody', 'experience', 'experiences',
})

_HOW_TO_SIGNALS = frozenset({
    'how', 'setup', 'configure', 'install', 'tutorial', 'guide',
    'step', 'steps', 'instructions',
})

_COMPARISON_SIGNALS = frozenset({
    'vs', 'versus', 'compared', 'comparison', 'better', 'alternative',
    'alternatives', 'difference', 'differences',
})

_PRODUCT_SIGNALS = frozenset({
    'pricing', 'price', 'cost', 'plan', 'plans', 'tier', 'tiers',
    'buy', 'purchase', 'subscription', 'trial', 'free',
})


def detect_query_type(topic: str) -> str:
    """Classify query intent without an LLM.

    Returns one of: "product", "concept", "opinion", "how_to", "comparison".
    Used to adapt per-platform query construction.
    """
    words = set(topic.lower().split())

    if words & _COMPARISON_SIGNALS:
        return "comparison"
    if words & _HOW_TO_SIGNALS or topic.lower().startswith("how "):
        return "how_to"
    if words & _OPINION_SIGNALS:
        return "opinion"
    if words & _PRODUCT_SIGNALS:
        return "product"
    return "concept"


def extract_compound_terms(topic: str) -> List[str]:
    """Detect multi-word terms that should be quoted in search queries.

    Identifies:
    - Hyphenated terms: "multi-agent", "vc-backed"
    - Title-cased multi-word names: "Claude Code", "React Native"

    Returns list of terms suitable for quoting (e.g., '"multi-agent"').
    """
    terms: List[str] = []

    # Hyphenated terms
    for match in re.finditer(r'\b\w+-\w+(?:-\w+)*\b', topic):
        terms.append(match.group())

    # Title-cased sequences (2+ capitalized words in a row)
    for match in re.finditer(r'(?:[A-Z][a-z]+\s+){1,}[A-Z][a-z]+', topic):
        terms.append(match.group())

    return terms
