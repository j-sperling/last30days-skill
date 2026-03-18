"""Gemini Google Search grounding as first-class web retrieval."""

from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urlparse

from . import dates, providers, schema


def grounded_search(
    provider: object,
    *,
    model: str,
    topic: str,
    subquery: schema.SubQuery,
    date_range: tuple[str, str],
    depth: str,
) -> tuple[list[dict], dict]:
    """Run Gemini Google Search grounding for a subquery."""
    if not hasattr(provider, "ground_search"):
        return [], {}

    from_date, to_date = date_range
    prompt = f"""
Search the public web for evidence relevant to this last-30-days research query.

Topic: {topic}
Subquery label: {subquery.label}
Search query: {subquery.search_query}
Ranking query: {subquery.ranking_query}
Date range: {from_date} to {to_date}

Prefer recent reporting, primary sources, and direct evidence.
""".strip()
    payload = provider.ground_search(model, prompt)
    items = _items_from_grounding_payload(payload, subquery.label, date_range)
    if depth == "deep" and items and hasattr(provider, "url_context_json"):
        _refine_with_url_context(provider, model, subquery, items)
    artifact = _artifact_from_payload(payload, subquery.label)
    return items, artifact


def _items_from_grounding_payload(
    payload: dict,
    label: str,
    date_range: tuple[str, str],
) -> list[dict]:
    from_date, to_date = date_range
    metadata = _grounding_metadata(payload)
    chunks = metadata.get("groundingChunks") or []
    supports = metadata.get("groundingSupports") or []
    answer_text = _grounding_answer_text(payload)

    support_map: dict[int, list[str]] = {}
    for support in supports:
        text = ((support.get("segment") or {}).get("text") or "").strip()
        if not text:
            continue
        for index in support.get("groundingChunkIndices") or []:
            support_map.setdefault(int(index), []).append(text)

    items = []
    for index, chunk in enumerate(chunks):
        web = chunk.get("web") or {}
        url = str(web.get("uri") or "").strip()
        if not url:
            continue
        snippet = " ".join(dict.fromkeys(support_map.get(index, []))).strip()
        title = str(web.get("title") or "").strip()
        published_at = _extract_grounding_date(
            web=web,
            support_texts=support_map.get(index, []),
            from_date=from_date,
            to_date=to_date,
            url=url,
        )
        items.append(
            {
                "id": f"WG{index + 1}",
                "title": title or _domain(url),
                "url": url,
                "source_domain": _domain(url),
                "snippet": snippet,
                "date": published_at,
                "relevance": 0.8,
                "why_relevant": f"Gemini Google Search grounding ({label})",
                "metadata": {
                    "grounding_query_label": label,
                    "grounding_chunk_index": index,
                    "supports": support_map.get(index, []),
                    "grounded_answer_excerpt": answer_text[:400] if answer_text else "",
                },
            }
        )
    return items


def _refine_with_url_context(provider: object, model: str, subquery: schema.SubQuery, items: list[dict]) -> None:
    urls = [item["url"] for item in items[:3]]
    if not urls:
        return
    prompt = """
Read these URLs and return JSON only:
{"snippets":[{"url":"...","snippet":"high-signal evidence snippet"}]}

Focus on what is directly relevant to this question:
{question}

URLs:
{urls}
""".strip().format(
        question=subquery.ranking_query,
        urls="\n".join(f"- {url}" for url in urls),
    )
    try:
        result = provider.url_context_json(model, prompt)
    except Exception as exc:
        import sys
        print(f"[Grounding] URL context refinement failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return
    snippet_by_url = {
        str(entry.get("url") or "").strip(): str(entry.get("snippet") or "").strip()
        for entry in result.get("snippets") or []
        if isinstance(entry, dict)
    }
    for item in items:
        snippet = snippet_by_url.get(item["url"])
        if snippet:
            item["snippet"] = snippet
            item.setdefault("metadata", {})["url_context_refined"] = True


def _artifact_from_payload(payload: dict, label: str) -> dict:
    metadata = _grounding_metadata(payload)
    return {
        "label": label,
        "answerText": _grounding_answer_text(payload),
        "webSearchQueries": metadata.get("webSearchQueries") or [],
        "searchEntryPoint": metadata.get("searchEntryPoint"),
        "groundingChunks": metadata.get("groundingChunks") or [],
        "groundingSupports": metadata.get("groundingSupports") or [],
    }


def _grounding_metadata(payload: dict) -> dict:
    for candidate in payload.get("candidates") or []:
        metadata = candidate.get("groundingMetadata")
        if isinstance(metadata, dict):
            return metadata
    return {}


def _grounding_answer_text(payload: dict) -> str:
    return providers.extract_gemini_text(payload).strip()


def _extract_grounding_date(
    *,
    web: dict,
    support_texts: list[str],
    from_date: str,
    to_date: str,
    url: str,
) -> str | None:
    for key in ("published_at", "publishedAt", "publicationDate", "date", "time"):
        value = _normalize_date_candidate(web.get(key))
        if _in_range(value, from_date, to_date):
            return value

    value = _extract_date_from_url(url)
    if _in_range(value, from_date, to_date):
        return value

    for text in support_texts:
        value = _extract_labeled_date(text)
        if _in_range(value, from_date, to_date):
            return value

    return None


def _normalize_date_candidate(value: object) -> str | None:
    if value is None:
        return None
    parsed = dates.parse_date(str(value).strip())
    if not parsed:
        return None
    return parsed.date().isoformat()


def _in_range(value: str | None, from_date: str, to_date: str) -> bool:
    return bool(value) and from_date <= value <= to_date


def _extract_date_from_url(url: str) -> str | None:
    patterns = [
        r"/(20\d{2})/(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])(?:/|$)",
        r"(20\d{2})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if not match:
            continue
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return None


def _extract_labeled_date(text: str) -> str | None:
    if not text:
        return None
    patterns = [
        r"(?i)\b(?:published|updated)\s*:?\s*(20\d{2}-\d{2}-\d{2})",
        r"(?i)\b(?:published|updated)\s*:?\s*([A-Z][a-z]+ \d{1,2}, 20\d{2})",
        r"(?i)\b(?:published|updated)\s*:?\s*(\d{1,2} [A-Z][a-z]+ 20\d{2})",
    ]
    formats = ["%Y-%m-%d", "%B %d, %Y", "%d %B %Y"]
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        value = match.group(1).strip()
        normalized = _normalize_date_candidate(value)
        if normalized:
            return normalized
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt).date().isoformat()
            except ValueError:
                continue
    return None


def _domain(url: str) -> str:
    return urlparse(url).netloc.strip().lower()
