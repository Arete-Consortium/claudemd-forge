"""Tests for model adapters."""

from __future__ import annotations

import types
from unittest.mock import MagicMock, patch

import pytest

from anchormd.drift.adapters import get_adapter
from anchormd.drift.adapters.anthropic import AnthropicAdapter
from anchormd.drift.adapters.base import ModelAdapter
from anchormd.drift.adapters.google import GoogleAdapter
from anchormd.drift.adapters.ollama import OllamaAdapter
from anchormd.drift.adapters.openai import OpenAIAdapter
from anchormd.exceptions import DriftError


class TestGetAdapter:
    def test_anthropic_claude(self) -> None:
        adapter = get_adapter("claude-3-haiku")
        assert isinstance(adapter, AnthropicAdapter)

    def test_anthropic_prefixed(self) -> None:
        adapter = get_adapter("anthropic/claude-3-opus")
        assert isinstance(adapter, AnthropicAdapter)
        assert adapter.name() == "claude-3-opus"

    def test_openai_gpt(self) -> None:
        adapter = get_adapter("gpt-4o")
        assert isinstance(adapter, OpenAIAdapter)

    def test_openai_o1(self) -> None:
        adapter = get_adapter("o1-preview")
        assert isinstance(adapter, OpenAIAdapter)

    def test_openai_o3(self) -> None:
        adapter = get_adapter("o3-mini")
        assert isinstance(adapter, OpenAIAdapter)

    def test_openai_prefixed(self) -> None:
        adapter = get_adapter("openai/gpt-4")
        assert isinstance(adapter, OpenAIAdapter)
        assert adapter.name() == "gpt-4"

    def test_google_gemini(self) -> None:
        adapter = get_adapter("gemini-pro")
        assert isinstance(adapter, GoogleAdapter)

    def test_google_prefixed(self) -> None:
        adapter = get_adapter("google/gemini-pro")
        assert isinstance(adapter, GoogleAdapter)
        assert adapter.name() == "gemini-pro"

    def test_ollama(self) -> None:
        adapter = get_adapter("ollama/llama3")
        assert isinstance(adapter, OllamaAdapter)
        assert adapter.name() == "ollama/llama3"

    def test_unknown_model(self) -> None:
        with pytest.raises(DriftError, match="Unknown model"):
            get_adapter("mystery-model-9000")

    def test_case_insensitive(self) -> None:
        adapter = get_adapter("Claude-3-haiku")
        assert isinstance(adapter, AnthropicAdapter)


class TestAnthropicAdapter:
    def test_missing_sdk(self) -> None:
        adapter = AnthropicAdapter("claude-3-haiku")
        with (
            patch.dict("sys.modules", {"anthropic": None}),
            pytest.raises(DriftError, match="anthropic SDK not installed"),
        ):
            adapter.complete("hello")

    def test_missing_api_key(self) -> None:
        fake_anthropic = types.ModuleType("anthropic")
        fake_anthropic.Anthropic = MagicMock  # type: ignore[attr-defined]
        adapter = AnthropicAdapter("claude-3-haiku")
        with (
            patch.dict("sys.modules", {"anthropic": fake_anthropic}),
            patch.dict("os.environ", {}, clear=True),
            pytest.raises(DriftError, match="ANTHROPIC_API_KEY"),
        ):
            adapter.complete("hello")

    def test_complete_success(self) -> None:
        fake_anthropic = types.ModuleType("anthropic")
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Hello back!")]
        mock_client.messages.create.return_value = mock_response
        fake_anthropic.Anthropic = MagicMock(return_value=mock_client)  # type: ignore[attr-defined]

        adapter = AnthropicAdapter("claude-3-haiku")
        with (
            patch.dict("sys.modules", {"anthropic": fake_anthropic}),
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
        ):
            result = adapter.complete("hello", system="be helpful")
        assert result == "Hello back!"
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["system"] == "be helpful"

    def test_name(self) -> None:
        assert AnthropicAdapter("claude-3-haiku").name() == "claude-3-haiku"


class TestOpenAIAdapter:
    def test_missing_sdk(self) -> None:
        adapter = OpenAIAdapter("gpt-4o")
        with (
            patch.dict("sys.modules", {"openai": None}),
            pytest.raises(DriftError, match="openai SDK not installed"),
        ):
            adapter.complete("hello")

    def test_missing_api_key(self) -> None:
        fake_openai = types.ModuleType("openai")
        fake_openai.OpenAI = MagicMock  # type: ignore[attr-defined]
        adapter = OpenAIAdapter("gpt-4o")
        with (
            patch.dict("sys.modules", {"openai": fake_openai}),
            patch.dict("os.environ", {}, clear=True),
            pytest.raises(DriftError, match="OPENAI_API_KEY"),
        ):
            adapter.complete("hello")

    def test_complete_success(self) -> None:
        fake_openai = types.ModuleType("openai")
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "GPT says hi"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response
        fake_openai.OpenAI = MagicMock(return_value=mock_client)  # type: ignore[attr-defined]

        adapter = OpenAIAdapter("gpt-4o")
        with (
            patch.dict("sys.modules", {"openai": fake_openai}),
            patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}),
        ):
            result = adapter.complete("hello", system="be helpful")
        assert result == "GPT says hi"

    def test_name(self) -> None:
        assert OpenAIAdapter("gpt-4o").name() == "gpt-4o"


class TestGoogleAdapter:
    def test_missing_sdk(self) -> None:
        adapter = GoogleAdapter("gemini-pro")
        with (
            patch.dict("sys.modules", {"google": None, "google.generativeai": None}),
            pytest.raises(DriftError, match="google-generativeai SDK not installed"),
        ):
            adapter.complete("hello")

    def test_missing_api_key(self) -> None:
        fake_google = types.ModuleType("google")
        fake_genai = types.ModuleType("google.generativeai")
        fake_genai.configure = MagicMock()  # type: ignore[attr-defined]
        fake_genai.GenerativeModel = MagicMock()  # type: ignore[attr-defined]
        adapter = GoogleAdapter("gemini-pro")
        with (
            patch.dict(
                "sys.modules",
                {"google": fake_google, "google.generativeai": fake_genai},
            ),
            patch.dict("os.environ", {}, clear=True),
            pytest.raises(DriftError, match="GOOGLE_API_KEY"),
        ):
            adapter.complete("hello")

    def test_name(self) -> None:
        assert GoogleAdapter("gemini-pro").name() == "gemini-pro"


class TestOllamaAdapter:
    def test_missing_httpx(self) -> None:
        adapter = OllamaAdapter("llama3")
        with (
            patch.dict("sys.modules", {"httpx": None}),
            pytest.raises(DriftError, match="httpx not installed"),
        ):
            adapter.complete("hello")

    def test_complete_success(self) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Ollama says hi"}
        mock_response.raise_for_status = MagicMock()

        adapter = OllamaAdapter("llama3")
        with patch("httpx.post", return_value=mock_response) as mock_post:
            result = adapter.complete("hello", system="be helpful")
        assert result == "Ollama says hi"
        call_kwargs = mock_post.call_args
        assert call_kwargs[1]["json"]["system"] == "be helpful"

    def test_http_error(self) -> None:
        import httpx

        adapter = OllamaAdapter("llama3")
        with (
            patch("httpx.post", side_effect=httpx.ConnectError("refused")),
            pytest.raises(DriftError, match="Ollama request failed"),
        ):
            adapter.complete("hello")

    def test_invalid_json_response(self) -> None:
        import json

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError("", "", 0)
        mock_response.text = "not json"

        adapter = OllamaAdapter("llama3")
        with (
            patch("httpx.post", return_value=mock_response),
            pytest.raises(DriftError, match="invalid JSON"),
        ):
            adapter.complete("hello")

    def test_custom_host(self) -> None:
        with patch.dict("os.environ", {"OLLAMA_HOST": "http://custom:1234"}):
            adapter = OllamaAdapter("llama3")
            assert adapter._host == "http://custom:1234"

    def test_name(self) -> None:
        assert OllamaAdapter("llama3").name() == "ollama/llama3"


class TestModelAdapterABC:
    def test_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            ModelAdapter()  # type: ignore[abstract]
