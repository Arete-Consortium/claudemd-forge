"""Model adapters for drift detection.

Each adapter wraps a specific LLM SDK behind a common interface.
The factory auto-detects the provider from the model string.
"""

from __future__ import annotations

from anchormd.drift.adapters.base import ModelAdapter
from anchormd.exceptions import DriftError


def get_adapter(model: str) -> ModelAdapter:
    """Return the appropriate adapter for *model*.

    Auto-detection rules:
    - ``claude-*`` or ``anthropic/*`` → Anthropic
    - ``gpt-*``, ``o1*``, ``o3*``, or ``openai/*`` → OpenAI
    - ``gemini-*`` or ``google/*`` → Google
    - ``ollama/*`` → Ollama
    """
    lower = model.lower()

    if lower.startswith("claude-") or lower.startswith("anthropic/"):
        from anchormd.drift.adapters.anthropic import AnthropicAdapter

        name = model.removeprefix("anthropic/")
        return AnthropicAdapter(name)

    if (
        lower.startswith("gpt-")
        or lower.startswith("o1")
        or lower.startswith("o3")
        or lower.startswith("openai/")
    ):
        from anchormd.drift.adapters.openai import OpenAIAdapter

        name = model.removeprefix("openai/")
        return OpenAIAdapter(name)

    if lower.startswith("gemini-") or lower.startswith("google/"):
        from anchormd.drift.adapters.google import GoogleAdapter

        name = model.removeprefix("google/")
        return GoogleAdapter(name)

    if lower.startswith("ollama/"):
        from anchormd.drift.adapters.ollama import OllamaAdapter

        name = model.removeprefix("ollama/")
        return OllamaAdapter(name)

    raise DriftError(
        f"Unknown model '{model}'. Prefix with a provider "
        "(e.g. ollama/llama3, anthropic/claude-3-haiku)."
    )
