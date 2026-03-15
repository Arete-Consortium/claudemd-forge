"""Tests for drift fixer."""

from __future__ import annotations

import json

import pytest

from anchormd.drift.adapters.base import ModelAdapter
from anchormd.drift.fixer import FixSuggestion, suggest_fixes
from anchormd.drift.models import (
    BenchmarkResult,
    CheckResult,
    CheckType,
    DriftSeverity,
    RunRecord,
)
from anchormd.exceptions import DriftError


class FakeFixerAdapter(ModelAdapter):
    def __init__(self, response: str) -> None:
        self._response = response

    def complete(self, prompt: str, system: str | None = None) -> str:
        return self._response

    def name(self) -> str:
        return "fake-fixer"


def _make_failing_run() -> RunRecord:
    return RunRecord(
        run_id="fix_test",
        timestamp="2026-03-01T12:00:00Z",
        model="test",
        score=0.5,
        delta=-0.2,
        severity=DriftSeverity.CRITICAL,
        results=[
            BenchmarkResult(
                benchmark_id="snake_case",
                score=0.5,
                checks=[
                    CheckResult(
                        type=CheckType.PATTERN_PRESENT,
                        passed=False,
                        message="Should use snake_case",
                    ),
                    CheckResult(type=CheckType.PATTERN_ABSENT, passed=True),
                ],
            )
        ],
    )


def _make_passing_run() -> RunRecord:
    return RunRecord(
        run_id="pass_test",
        timestamp="2026-03-01T12:00:00Z",
        model="test",
        score=1.0,
        delta=0.0,
        severity=DriftSeverity.STABLE,
        results=[
            BenchmarkResult(
                benchmark_id="test",
                score=1.0,
                checks=[CheckResult(type=CheckType.PATTERN_PRESENT, passed=True)],
            )
        ],
    )


class TestSuggestFixes:
    def test_basic_suggestion(self) -> None:
        response = json.dumps(
            [
                {
                    "benchmark_id": "snake_case",
                    "description": "Add snake_case rule",
                    "claude_md_addition": "Always use snake_case for Python functions.",
                    "confidence": 0.9,
                }
            ]
        )
        adapter = FakeFixerAdapter(response)
        suggestions = suggest_fixes(_make_failing_run(), [], adapter)
        assert len(suggestions) == 1
        assert suggestions[0].benchmark_id == "snake_case"
        assert suggestions[0].confidence == 0.9

    def test_no_failures(self) -> None:
        adapter = FakeFixerAdapter("[]")
        suggestions = suggest_fixes(_make_passing_run(), [], adapter)
        assert suggestions == []

    def test_json_in_fence(self) -> None:
        inner = json.dumps(
            [
                {
                    "benchmark_id": "test",
                    "description": "Fix",
                    "claude_md_addition": "Add rule",
                    "confidence": 0.8,
                }
            ]
        )
        response = f"Here are my suggestions:\n```json\n{inner}\n```"
        adapter = FakeFixerAdapter(response)
        suggestions = suggest_fixes(_make_failing_run(), [], adapter)
        assert len(suggestions) == 1

    def test_unparseable_response(self) -> None:
        adapter = FakeFixerAdapter("No JSON here at all.")
        with pytest.raises(DriftError, match="no JSON"):
            suggest_fixes(_make_failing_run(), [], adapter)

    def test_adapter_failure(self) -> None:
        class FailAdapter(ModelAdapter):
            def complete(self, prompt: str, system: str | None = None) -> str:
                raise RuntimeError("API error")

            def name(self) -> str:
                return "fail"

        with pytest.raises(DriftError, match="Failed to generate fix"):
            suggest_fixes(_make_failing_run(), [], FailAdapter())

    def test_skips_invalid_suggestions(self) -> None:
        response = json.dumps(
            [
                {"invalid": "item"},
                {
                    "benchmark_id": "valid",
                    "description": "Fix",
                    "claude_md_addition": "Add rule",
                    "confidence": 0.7,
                },
            ]
        )
        adapter = FakeFixerAdapter(response)
        suggestions = suggest_fixes(_make_failing_run(), [], adapter)
        assert len(suggestions) == 1
        assert suggestions[0].benchmark_id == "valid"


class TestFixSuggestionModel:
    def test_basic(self) -> None:
        s = FixSuggestion(
            benchmark_id="test",
            description="Fix something",
            claude_md_addition="Add this rule",
            confidence=0.85,
        )
        assert s.benchmark_id == "test"
        assert s.confidence == 0.85
