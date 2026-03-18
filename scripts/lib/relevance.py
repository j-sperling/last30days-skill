"""Shared token-overlap relevance scoring for search result ranking.

The score is intentionally query-centric:
- exact phrase matches should score very high
- partial matches should pay a meaningful penalty
- matches on generic words alone ("odds", "review") should not pass as relevant
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

# Generic query words that should not carry relevance on their own.
# They still help when paired with stronger entity/topic matches.
LOW_SIGNAL_QUERY_TOKENS = frozenset({
    'advice', 'animation', 'animations', 'best', 'chance', 'chances',
    'code', 'compare', 'comparison', 'differences', 'explain', 'guide',
    'guides', 'how', 'latest', 'news', 'odds', 'opinion', 'opinions',
    'prediction', 'predictions', 'probability', 'probabilities', 'prompt',
    'prompting', 'prompts', 'rate', 'review', 'reviews', 'thoughts',
    'tip', 'tips', 'tutorial', 'tutorials', 'update', 'updates', 'use',
    'using', 'versus', 'vs', 'worth',
})


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


def _normalize_phrase(text: str) -> str:
    """Normalize text for phrase containment checks."""
    return ' '.join(re.sub(r'[^\w\s]', ' ', text.lower()).split())


def _score_tokens(
    q_tokens: Set[str],
    t_tokens: Set[str],
    combined: str,
    query: str,
) -> float:
    """Core scoring logic shared by the plain and title-weighted paths."""
    overlap_tokens = q_tokens & t_tokens
    overlap = len(overlap_tokens)
    if overlap == 0:
        return 0.0

    informative_q_tokens = {t for t in q_tokens if t not in LOW_SIGNAL_QUERY_TOKENS}
    if not informative_q_tokens:
        informative_q_tokens = q_tokens

    coverage = overlap / len(q_tokens)
    informative_overlap = len(informative_q_tokens & t_tokens) / len(informative_q_tokens)
    precision_denominator = min(len(t_tokens), len(q_tokens) + 4) or 1
    precision = overlap / precision_denominator

    phrase_bonus = 0.0
    normalized_query = _normalize_phrase(query)
    normalized_text = _normalize_phrase(combined)
    if normalized_query and normalized_query in normalized_text:
        phrase_bonus = 0.12 if len(normalized_query.split()) > 1 else 0.16

    base = (
        0.55 * (coverage ** 1.35) +
        0.25 * informative_overlap +
        0.20 * precision
    )

    # If we only matched generic query words, keep the score below the
    # normal relevance filter threshold so these do not survive by default.
    if informative_q_tokens and not (informative_q_tokens & t_tokens):
        return round(min(0.24, base), 2)

    return round(min(1.0, base + phrase_bonus), 2)


def token_overlap_relevance(
    query: str,
    text: str,
    *,
    title: Optional[str] = None,
    hashtags: Optional[List[str]] = None,
) -> float:
    """Compute a query-centric relevance score between 0.0 and 1.0.

    The score combines:
    - query coverage
    - informative-token coverage
    - a small precision term to penalize extra noise
    - an exact phrase bonus

    When *title* is provided, title matches are weighted 3x over body matches
    (60/40 blend) so that items with relevant titles but long dilutive bodies
    (e.g. grounding/web search results) are not unfairly penalized.

    Generic tokens alone are capped below the post-retrieval 0.3 threshold.

    Args:
        query: Search query
        text: Content text to match against
        title: Optional title text. When provided, title and body are scored
            separately and blended (0.6 title + 0.4 body).
        hashtags: Optional list of hashtags (TikTok/Instagram). Concatenated
            hashtags are split to match query tokens (e.g. "claudecode" matches "claude").

    Returns:
        Float between 0.0 and 1.0 (0.5 for empty queries)
    """
    q_tokens = tokenize(query)

    if not q_tokens:
        return 0.5  # Neutral fallback for empty/stopword-only queries

    # Combine text and hashtags for matching
    combined = text
    if hashtags:
        combined = f"{text} {' '.join(hashtags)}"

    def _expand_hashtags(tokens: Set[str]) -> Set[str]:
        if not hashtags:
            return tokens
        for tag in hashtags:
            tag_lower = tag.lower()
            for qt in q_tokens:
                if qt in tag_lower and qt != tag_lower:
                    tokens.add(qt)
        return tokens

    # Title-weighted path: score title and body separately, blend 60/40
    if title:
        title_tokens = _expand_hashtags(tokenize(title))
        body_tokens = _expand_hashtags(tokenize(combined))
        title_score = _score_tokens(q_tokens, title_tokens, title, query)
        body_score = _score_tokens(q_tokens, body_tokens, combined, query)
        return round(min(1.0, 0.6 * title_score + 0.4 * body_score), 2)

    # Default path: score combined text as before
    t_tokens = tokenize(combined)
    t_tokens = _expand_hashtags(t_tokens)

    return _score_tokens(q_tokens, t_tokens, combined, query)
