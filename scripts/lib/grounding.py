"""Web search retrieval via Brave Search and Serper."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime
from urllib.parse import urlparse

from . import dates


# ---------------------------------------------------------------------------
# Brave Search API
# ---------------------------------------------------------------------------

def brave_search(
    query: str, date_range: tuple[str, str], api_key: str, count: int = 5,
) -> tuple[list[dict], dict]:
    url = f"https://api.search.brave.com/res/v1/web/search?q={urllib.parse.quote(query)}&count={count}"
    req = urllib.request.Request(url, headers={"X-Subscription-Token": api_key})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    items = []
    for i, r in enumerate((data.get("web", {}).get("results", []))[:count]):
        raw_date = r.get("page_age") or ""
        pub_date = _normalize_date(raw_date[:10]) if raw_date else None
        items.append({
            "id": f"WB{i + 1}",
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "source_domain": _domain(r.get("url", "")),
            "snippet": r.get("description", ""),
            "date": pub_date,
            "relevance": 0.8,
            "why_relevant": "Brave web search",
        })
    artifact = {"label": "brave", "webSearchQueries": [query], "resultCount": len(items)}
    return items, artifact


# ---------------------------------------------------------------------------
# Serper (Google Search wrapper)
# ---------------------------------------------------------------------------

def serper_search(
    query: str, date_range: tuple[str, str], api_key: str, count: int = 5,
) -> tuple[list[dict], dict]:
    payload = json.dumps({"q": query, "num": count}).encode()
    req = urllib.request.Request(
        "https://google.serper.dev/search", data=payload,
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    items = []
    for i, r in enumerate((data.get("organic", []))[:count]):
        raw_date = r.get("date") or ""
        pub_date = _parse_serper_date(raw_date)
        items.append({
            "id": f"WS{i + 1}",
            "title": r.get("title", ""),
            "url": r.get("link", ""),
            "source_domain": _domain(r.get("link", "")),
            "snippet": r.get("snippet", ""),
            "date": pub_date,
            "relevance": 0.8,
            "why_relevant": "Serper web search",
        })
    artifact = {"label": "serper", "webSearchQueries": [query], "resultCount": len(items)}
    return items, artifact


def _parse_serper_date(raw: str) -> str | None:
    if not raw:
        return None
    normalized = _normalize_date(raw)
    if normalized:
        return normalized
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def web_search(
    query: str,
    date_range: tuple[str, str],
    config: dict,
    backend: str = "auto",
) -> tuple[list[dict], dict]:
    """Run web search with the specified or auto-detected backend."""
    if backend == "auto":
        if config.get("BRAVE_API_KEY"):
            backend = "brave"
        elif config.get("SERPER_API_KEY"):
            backend = "serper"
        else:
            return [], {}
    if backend == "brave":
        return brave_search(query, date_range, config.get("BRAVE_API_KEY", ""))
    if backend == "serper":
        return serper_search(query, date_range, config.get("SERPER_API_KEY", ""))
    return [], {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_date(value: object) -> str | None:
    if value is None:
        return None
    parsed = dates.parse_date(str(value).strip())
    if not parsed:
        return None
    return parsed.date().isoformat()


def _domain(url: str) -> str:
    return urlparse(url).netloc.strip().lower()
