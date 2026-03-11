"""Shared relevance scoring for /last30days search modules.

Consolidates duplicated _tokenize, _compute_relevance, STOPWORDS, and SYNONYMS
from youtube_yt, tiktok, instagram, and scrapecreators_x into one module.
"""

import re
from typing import List, Optional, Set

# Stopwords for relevance computation (common English words that dilute token overlap)
STOPWORDS = frozenset({
    'the', 'a', 'an', 'to', 'for', 'how', 'is', 'in', 'of', 'on',
    'and', 'with', 'from', 'by', 'at', 'this', 'that', 'it', 'my',
    'your', 'i', 'me', 'we', 'you', 'what', 'are', 'do', 'can',
    'its', 'be', 'or', 'not', 'no', 'so', 'if', 'but', 'about',
    'all', 'just', 'get', 'has', 'have', 'was', 'will',
})

# Synonym groups for relevance scoring (bidirectional expansion)
# Superset of all platform-specific synonym dicts
SYNONYMS = {
    'hip': {'rap', 'hiphop'},
    'hop': {'rap', 'hiphop'},
    'rap': {'hip', 'hop', 'hiphop'},
    'hiphop': {'rap', 'hip', 'hop'},
    'js': {'javascript'},
    'javascript': {'js'},
    'ts': {'typescript'},
    'typescript': {'ts'},
    'ai': {'artificial', 'intelligence'},
    'ml': {'machine', 'learning'},
    'react': {'reactjs'},
    'reactjs': {'react'},
    'svelte': {'sveltejs'},
    'sveltejs': {'svelte'},
    'vue': {'vuejs'},
    'vuejs': {'vue'},
}


def tokenize(text: str) -> Set[str]:
    """Lowercase, strip punctuation, remove stopwords, drop single-char tokens.

    Expands tokens with synonyms for better cross-domain matching.
    """
    words = re.sub(r'[^\w\s]', ' ', text.lower()).split()
    tokens = {w for w in words if w not in STOPWORDS and len(w) > 1}
    expanded = set(tokens)
    for t in tokens:
        if t in SYNONYMS:
            expanded.update(SYNONYMS[t])
    return expanded


def token_overlap_relevance(
    query: str,
    text: str,
    hashtags: Optional[List[str]] = None,
) -> float:
    """Compute relevance as ratio of query tokens found in text.

    Uses ratio overlap (intersection / query_length) so short queries
    score higher when fully represented in the text. Floors at 0.1.

    Args:
        query: Search query
        text: Content text to match against
        hashtags: Optional list of hashtags (TikTok/Instagram). Concatenated
            hashtags are split to match query tokens (e.g. "claudecode" matches "claude").

    Returns:
        Float between 0.1 and 1.0 (0.5 for empty queries)
    """
    q_tokens = tokenize(query)

    # Combine text and hashtags for matching
    combined = text
    if hashtags:
        combined = f"{text} {' '.join(hashtags)}"
    t_tokens = tokenize(combined)

    # Split concatenated hashtags (e.g., "claudecode" -> matches "claude", "code")
    if hashtags:
        for tag in hashtags:
            tag_lower = tag.lower()
            for qt in q_tokens:
                if qt in tag_lower and qt != tag_lower:
                    t_tokens.add(qt)

    if not q_tokens:
        return 0.5  # Neutral fallback for empty/stopword-only queries

    overlap = len(q_tokens & t_tokens)
    ratio = overlap / len(q_tokens)
    return max(0.1, min(1.0, ratio))
