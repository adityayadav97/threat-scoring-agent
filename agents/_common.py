"""Shared helpers for the LLM clients (errors, JSON parsing, provider factory)."""

from __future__ import annotations

import json
import os
from typing import Any


class LLMError(RuntimeError):
    """Raised when an LLM provider cannot be reached or returns bad data."""


def safe_json_loads(raw: str) -> dict[str, Any]:
    """Parse JSON, tolerating markdown code fences the model may add."""
    if not raw:
        raise LLMError("Model returned an empty response.")
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        # Drop the opening fence (``` or ```json) and the trailing fence.
        cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3]
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMError(
            f"Could not parse JSON from model response: {exc}\nRaw: {raw[:500]}"
        ) from exc


def build_client(api_key: str | None = None, model: str | None = None, provider: str | None = None):
    """Create an LLM client, preferring Groq when a Groq key is available.

    Provider selection order:
        1. explicit ``provider`` argument
        2. ``LLM_PROVIDER`` env var
        3. "groq" if ``GROQ_API_KEY`` is set, else "gemini"
    """
    provider = (
        provider
        or os.getenv("LLM_PROVIDER")
        or ("groq" if os.getenv("GROQ_API_KEY") else "gemini")
    ).lower()

    if provider == "groq":
        from .groq_client import GroqClient

        return GroqClient(api_key=api_key, model=model)

    from .gemini_client import GeminiClient

    return GeminiClient(api_key=api_key, model=model)
