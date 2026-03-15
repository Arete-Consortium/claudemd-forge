"""Abstract base class for LLM model adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ModelAdapter(ABC):
    """Interface every provider adapter must implement."""

    @abstractmethod
    def complete(self, prompt: str, system: str | None = None) -> str:
        """Send *prompt* (with optional *system* message) and return the response text."""

    @abstractmethod
    def name(self) -> str:
        """Return a human-readable model identifier."""
