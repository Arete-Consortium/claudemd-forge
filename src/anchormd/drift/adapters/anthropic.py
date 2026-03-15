"""Anthropic (Claude) model adapter."""

from __future__ import annotations

import os

from anchormd.drift.adapters.base import ModelAdapter
from anchormd.exceptions import DriftError


class AnthropicAdapter(ModelAdapter):
    """Adapter for Anthropic Claude models."""

    def __init__(self, model: str) -> None:
        self._model = model

    def complete(self, prompt: str, system: str | None = None) -> str:
        try:
            import anthropic
        except ImportError as exc:
            raise DriftError("anthropic SDK not installed. Run: pip install anthropic") from exc

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise DriftError("ANTHROPIC_API_KEY environment variable not set.")

        client = anthropic.Anthropic(api_key=api_key)
        kwargs: dict = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        response = client.messages.create(**kwargs)
        return response.content[0].text  # type: ignore[union-attr]

    def name(self) -> str:
        return self._model
