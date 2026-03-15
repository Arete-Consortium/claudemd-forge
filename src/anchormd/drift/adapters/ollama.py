"""Ollama (local) model adapter."""

from __future__ import annotations

import json
import os

from anchormd.drift.adapters.base import ModelAdapter
from anchormd.exceptions import DriftError


class OllamaAdapter(ModelAdapter):
    """Adapter for locally-hosted Ollama models."""

    def __init__(self, model: str) -> None:
        self._model = model
        self._host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    def complete(self, prompt: str, system: str | None = None) -> str:
        try:
            import httpx
        except ImportError as exc:
            raise DriftError("httpx not installed. Run: pip install httpx") from exc

        payload: dict = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            payload["system"] = system

        try:
            resp = httpx.post(
                f"{self._host.rstrip('/')}/api/generate",
                json=payload,
                timeout=120.0,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise DriftError(f"Ollama request failed: {exc}") from exc

        try:
            data = resp.json()
        except json.JSONDecodeError as exc:
            raise DriftError(f"Ollama returned invalid JSON: {resp.text[:200]}") from exc

        return data.get("response", "")

    def name(self) -> str:
        return f"ollama/{self._model}"
