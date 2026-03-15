"""Tests for drift benchmark generator."""

from __future__ import annotations

import json

import pytest

from anchormd.drift.adapters.base import ModelAdapter
from anchormd.drift.generator import generate_benchmarks
from anchormd.exceptions import DriftError


class FakeGeneratorAdapter(ModelAdapter):
    def __init__(self, response: str) -> None:
        self._response = response

    def complete(self, prompt: str, system: str | None = None) -> str:
        return self._response

    def name(self) -> str:
        return "fake-generator"


class TestGenerateBenchmarks:
    def test_valid_response(self) -> None:
        response = json.dumps(
            {
                "version": 1,
                "benchmarks": [
                    {
                        "id": "snake_case_test",
                        "prompt": "Write a Python function",
                        "checks": [
                            {
                                "type": "pattern_present",
                                "pattern": "def \\w+\\(",
                                "message": "Should use snake_case",
                            }
                        ],
                        "weight": 1.0,
                    }
                ],
            }
        )
        adapter = FakeGeneratorAdapter(response)
        suite = generate_benchmarks("# My CLAUDE.md\nUse snake_case.", adapter)
        assert len(suite.benchmarks) == 1
        assert suite.benchmarks[0].id == "snake_case_test"

    def test_json_in_markdown_fence(self) -> None:
        inner = json.dumps(
            {
                "version": 1,
                "benchmarks": [
                    {
                        "id": "test",
                        "prompt": "Do something",
                        "checks": [],
                        "weight": 1.0,
                    }
                ],
            }
        )
        response = f"Here are the benchmarks:\n```json\n{inner}\n```"
        adapter = FakeGeneratorAdapter(response)
        suite = generate_benchmarks("content", adapter)
        assert len(suite.benchmarks) == 1

    def test_json_with_preamble(self) -> None:
        inner = json.dumps(
            {
                "version": 1,
                "benchmarks": [{"id": "test", "prompt": "p", "checks": [], "weight": 1.0}],
            }
        )
        response = f"Sure! Here's the suite:\n{inner}\n\nHope that helps!"
        adapter = FakeGeneratorAdapter(response)
        suite = generate_benchmarks("content", adapter)
        assert len(suite.benchmarks) == 1

    def test_unparseable_response(self) -> None:
        adapter = FakeGeneratorAdapter("This is not JSON at all, no braces.")
        with pytest.raises(DriftError, match="no JSON"):
            generate_benchmarks("content", adapter)

    def test_invalid_json_in_braces(self) -> None:
        adapter = FakeGeneratorAdapter("Here: {invalid json here}")
        with pytest.raises(DriftError, match="unparseable JSON"):
            generate_benchmarks("content", adapter)

    def test_adapter_exception(self) -> None:
        class FailAdapter(ModelAdapter):
            def complete(self, prompt: str, system: str | None = None) -> str:
                raise RuntimeError("API down")

            def name(self) -> str:
                return "fail"

        with pytest.raises(DriftError, match="Failed to generate"):
            generate_benchmarks("content", FailAdapter())

    def test_skips_unknown_check_types(self) -> None:
        response = json.dumps(
            {
                "version": 1,
                "benchmarks": [
                    {
                        "id": "test",
                        "prompt": "p",
                        "checks": [
                            {"type": "unknown_type", "pattern": "x"},
                            {"type": "pattern_present", "pattern": "y"},
                        ],
                        "weight": 1.0,
                    }
                ],
            }
        )
        adapter = FakeGeneratorAdapter(response)
        suite = generate_benchmarks("content", adapter)
        assert len(suite.benchmarks[0].checks) == 1

    def test_missing_id_raises(self) -> None:
        response = json.dumps(
            {
                "version": 1,
                "benchmarks": [{"prompt": "p", "checks": []}],
            }
        )
        adapter = FakeGeneratorAdapter(response)
        with pytest.raises(DriftError, match="Failed to build"):
            generate_benchmarks("content", adapter)

    def test_multiple_benchmarks(self) -> None:
        response = json.dumps(
            {
                "version": 1,
                "benchmarks": [
                    {"id": "a", "prompt": "p1", "checks": [], "weight": 1.0},
                    {"id": "b", "prompt": "p2", "checks": [], "weight": 2.0},
                ],
            }
        )
        adapter = FakeGeneratorAdapter(response)
        suite = generate_benchmarks("content", adapter)
        assert len(suite.benchmarks) == 2
        assert suite.benchmarks[1].weight == 2.0
