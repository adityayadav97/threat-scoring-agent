"""Thin wrapper around the Google Gemini API (``google-genai`` SDK).

Centralises model configuration, API-key loading and JSON parsing so the
individual agents can stay focused on prompting and domain logic.
"""

from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")


class GeminiClientError(RuntimeError):
    """Raised when the Gemini API cannot be reached or returns bad data."""


class GeminiClient:
    """Small helper for text and structured-JSON generation with Gemini."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise GeminiClientError(
                "No Gemini API key found. Set GEMINI_API_KEY in your environment "
                "or .env file, or pass api_key explicitly."
            )
        self.model_name = model or DEFAULT_MODEL
        self._client = genai.Client(api_key=key)

    def generate_text(self, prompt: str, *, temperature: float = 0.2) -> str:
        """Return a plain-text completion for ``prompt``."""
        text = self._generate(prompt, temperature=temperature)
        if not text:
            raise GeminiClientError("Gemini returned an empty response.")
        return text.strip()

    def generate_json(self, prompt: str, *, temperature: float = 0.2) -> dict[str, Any]:
        """Return a parsed JSON object from a structured Gemini completion."""
        raw = self._generate(
            prompt, temperature=temperature, response_mime_type="application/json"
        )
        if not raw:
            raise GeminiClientError("Gemini returned an empty response.")
        return _safe_json_loads(raw)

    def _generate(
        self,
        prompt: str,
        *,
        temperature: float,
        response_mime_type: str | None = None,
    ) -> str | None:
        config = types.GenerateContentConfig(
            temperature=temperature,
            response_mime_type=response_mime_type,
        )
        try:
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )
        except Exception as exc:  # noqa: BLE001 - surface any SDK/transport error
            raise GeminiClientError(f"Gemini request failed: {exc}") from exc
        return getattr(response, "text", None)


def _safe_json_loads(raw: str) -> dict[str, Any]:
    """Parse JSON, tolerating markdown code fences the model may add."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        # Drop the opening fence (``` or ```json) and the trailing fence.
        cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3]
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise GeminiClientError(
            f"Could not parse JSON from Gemini response: {exc}\nRaw: {raw[:500]}"
        ) from exc
