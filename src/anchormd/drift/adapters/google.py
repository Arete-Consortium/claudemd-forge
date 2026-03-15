"""Google (Gemini) model adapter."""

from __future__ import annotations

import os

from anchormd.drift.adapters.base import ModelAdapter
from anchormd.exceptions import DriftError


class GoogleAdapter(ModelAdapter):
    """Adapter for Google Gemini models."""

    def __init__(self, model: str) -> None:
        self._model = model

    def complete(self, prompt: str, system: str | None = None) -> str:
        try:
            import google.generativeai as genai
        except ImportError as exc:
            raise DriftError(
                "google-generativeai SDK not installed. Run: pip install google-generativeai"
            ) from exc

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise DriftError("GOOGLE_API_KEY environment variable not set.")

        genai.configure(api_key=api_key)
        gen_model = genai.GenerativeModel(
            model_name=self._model,
            system_instruction=system,
        )
        response = gen_model.generate_content(prompt)
        return response.text

    def name(self) -> str:
        return self._model
