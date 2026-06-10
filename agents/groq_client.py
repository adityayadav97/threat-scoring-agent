"""LLM client backed by the Groq API (fast, OpenAI-compatible inference).

Exposes the same ``generate_text`` / ``generate_json`` interface as the Gemini
client so the agents can use either provider interchangeably.
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from groq import Groq

from ._common import LLMError, safe_json_loads

load_dotenv()

# A capable default that supports JSON mode on Groq.
DEFAULT_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

_JSON_SYSTEM = "You are a precise assistant. Respond ONLY with a single valid JSON object."


class GroqClient:
    """Small helper for text and structured-JSON generation with Groq."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        key = api_key or os.getenv("GROQ_API_KEY")
        if not key:
            raise LLMError(
                "No Groq API key found. Set GROQ_API_KEY in your environment, "
                ".env file, or Streamlit secrets, or pass api_key explicitly. "
                "Get a free key at https://console.groq.com/keys"
            )
        self.model_name = model or DEFAULT_MODEL
        self._client = Groq(api_key=key)

    def generate_text(self, prompt: str, *, temperature: float = 0.2) -> str:
        """Return a plain-text completion for ``prompt``."""
        content = self._chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )
        if not content:
            raise LLMError("Groq returned an empty response.")
        return content.strip()

    def generate_json(self, prompt: str, *, temperature: float = 0.2) -> dict[str, Any]:
        """Return a parsed JSON object from a structured Groq completion."""
        messages = [
            {"role": "system", "content": _JSON_SYSTEM},
            {"role": "user", "content": prompt},
        ]
        try:
            content = self._chat(
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"},
            )
        except LLMError:
            # Some models/accounts may not support JSON mode; retry plainly
            # and rely on the fence-tolerant parser.
            content = self._chat(messages=messages, temperature=temperature)
        return safe_json_loads(content or "")

    def _chat(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        response_format: dict[str, str] | None = None,
    ) -> str | None:
        kwargs: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format is not None:
            kwargs["response_format"] = response_format
        try:
            response = self._client.chat.completions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001 - surface any SDK/transport error
            raise LLMError(f"Groq request failed: {exc}") from exc
        return response.choices[0].message.content
