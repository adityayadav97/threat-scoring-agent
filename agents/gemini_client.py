"""Thin wrapper around the Google Gemini API (``google-genai`` SDK).

Centralises model configuration, API-key loading and JSON parsing so the
individual agents can stay focused on prompting and domain logic.
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

from ._common import LLMError, safe_json_loads

load_dotenv()

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")


class GeminiClientError(LLMError):
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
        return safe_json_loads(raw)

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
