"""OpenAI model adapter."""

from __future__ import annotations

import os

from anchormd.drift.adapters.base import ModelAdapter
from anchormd.exceptions import DriftError


class OpenAIAdapter(ModelAdapter):
    """Adapter for OpenAI GPT/o-series models."""

    def __init__(self, model: str) -> None:
        self._model = model

    def complete(self, prompt: str, system: str | None = None) -> str:
        try:
            import openai
        except ImportError as exc:
            raise DriftError("openai SDK not installed. Run: pip install openai") from exc

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise DriftError("OPENAI_API_KEY environment variable not set.")

        client = openai.OpenAI(api_key=api_key)
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=4096,
        )
        return response.choices[0].message.content or ""

    def name(self) -> str:
        return self._model
