"""Static provider catalog and runtime client implementations."""

from __future__ import annotations

import json
import re
from typing import Any


class ReasoningClient:
    """Shared interface for planner and rerank providers."""

    name: str

    def generate_text(
        self,
        model: str,
        prompt: str,
        *,
        tools: list[dict[str, Any]] | None = None,
        response_mime_type: str | None = None,
    ) -> str:
        raise NotImplementedError

    def generate_json(
        self,
        model: str,
        prompt: str,
        *,
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        text = self.generate_text(model, prompt, tools=tools, response_mime_type="application/json")
        return extract_json(text)


def extract_json(text: str) -> dict[str, Any]:
    """Extract the first JSON object from a model response."""
    text = text.strip()
    if not text:
        raise ValueError("Expected JSON response, got empty text")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise
        return json.loads(match.group(0))
