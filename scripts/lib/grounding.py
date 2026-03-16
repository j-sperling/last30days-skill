"""Gemini Google Search grounding as first-class web retrieval."""

from __future__ import annotations

from urllib.parse import urlparse

from . import schema


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
    items = _items_from_grounding_payload(payload, subquery.label)
    if depth == "deep" and items and hasattr(provider, "url_context_json"):
        _refine_with_url_context(provider, model, subquery, items)
    artifact = _artifact_from_payload(payload, subquery.label)
    return items, artifact


def _items_from_grounding_payload(payload: dict, label: str) -> list[dict]:
    metadata = _grounding_metadata(payload)
    chunks = metadata.get("groundingChunks") or []
    supports = metadata.get("groundingSupports") or []

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
        items.append(
            {
                "id": f"WG{index + 1}",
                "title": title or _domain(url),
                "url": url,
                "source_domain": _domain(url),
                "snippet": snippet,
                "date": None,
                "relevance": 0.8,
                "why_relevant": f"Gemini Google Search grounding ({label})",
                "metadata": {
                    "grounding_query_label": label,
                    "grounding_chunk_index": index,
                    "supports": support_map.get(index, []),
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
    except Exception:
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


def _domain(url: str) -> str:
    return urlparse(url).netloc.strip().lower()
