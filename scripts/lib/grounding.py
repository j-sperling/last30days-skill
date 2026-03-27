"""Web search retrieval via Brave Search and Serper."""

from __future__ import annotations

import urllib.parse
from datetime import datetime
from urllib.parse import urlparse

from . import dates, http


# ---------------------------------------------------------------------------
# Brave Search API
# ---------------------------------------------------------------------------

def brave_search(
    query: str, date_range: tuple[str, str], api_key: str, count: int = 5,
) -> tuple[list[dict], dict]:
    url = (
        "https://api.search.brave.com/res/v1/web/search?"
        + urllib.parse.urlencode(
            {
                "q": query,
                "count": count,
                "freshness": f"{date_range[0]}to{date_range[1]}",
            }
        )
    )
    data = http.request("GET", url, headers={"X-Subscription-Token": api_key}, timeout=15)
    items = []
    for i, r in enumerate((data.get("web", {}).get("results", []))[:count]):
        raw_date = r.get("page_age") or ""
        pub_date = _normalize_date(raw_date[:10]) if raw_date else None
        if not _in_date_range(pub_date, date_range):
            continue
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
    data = http.request(
        "POST", "https://google.serper.dev/search",
        headers={"X-API-KEY": api_key},
        json_data={"q": query, "num": count},
        timeout=15,
    )
    items = []
    for i, r in enumerate((data.get("organic", []))[:count]):
        raw_date = r.get("date") or ""
        pub_date = _parse_serper_date(raw_date)
        if not _in_date_range(pub_date, date_range):
            continue
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


def _in_date_range(pub_date: str | None, date_range: tuple[str, str]) -> bool:
    if not pub_date:
        return False
    return date_range[0] <= pub_date <= date_range[1]


def _domain(url: str) -> str:
    return urlparse(url).netloc.strip().lower()
