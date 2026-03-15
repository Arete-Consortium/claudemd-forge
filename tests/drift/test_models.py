"""Tests for drift data models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from anchormd.drift.models import (
    BenchmarkCheck,
    BenchmarkDef,
    BenchmarkResult,
    BenchmarkSuite,
    CheckResult,
    CheckType,
    DriftSeverity,
    RunRecord,
)


class TestCheckType:
    def test_values(self) -> None:
        assert CheckType.PATTERN_PRESENT == "pattern_present"
        assert CheckType.PATTERN_ABSENT == "pattern_absent"
        assert CheckType.LLM_JUDGE == "llm_judge"
        assert CheckType.LENGTH_RANGE == "length_range"
        assert CheckType.JSON_VALID == "json_valid"
        assert CheckType.CONTAINS_SECTIONS == "contains_sections"

    def test_is_str(self) -> None:
        assert isinstance(CheckType.PATTERN_PRESENT, str)


class TestDriftSeverity:
    def test_values(self) -> None:
        assert DriftSeverity.CRITICAL == "critical"
        assert DriftSeverity.WARNING == "warning"
        assert DriftSeverity.STABLE == "stable"
        assert DriftSeverity.IMPROVED == "improved"


class TestBenchmarkCheck:
    def test_defaults(self) -> None:
        check = BenchmarkCheck(type=CheckType.PATTERN_PRESENT, pattern="foo")
        assert check.threshold == 0.8
        assert check.message is None
        assert check.min_words is None
        assert check.max_words is None
        assert check.sections is None

    def test_threshold_bounds(self) -> None:
        with pytest.raises(ValidationError):
            BenchmarkCheck(type=CheckType.LLM_JUDGE, threshold=1.5)
        with pytest.raises(ValidationError):
            BenchmarkCheck(type=CheckType.LLM_JUDGE, threshold=-0.1)

    def test_length_range_fields(self) -> None:
        check = BenchmarkCheck(type=CheckType.LENGTH_RANGE, min_words=10, max_words=500)
        assert check.min_words == 10
        assert check.max_words == 500

    def test_sections_field(self) -> None:
        check = BenchmarkCheck(type=CheckType.CONTAINS_SECTIONS, sections=["Intro", "Conclusion"])
        assert check.sections == ["Intro", "Conclusion"]


class TestBenchmarkDef:
    def test_defaults(self) -> None:
        bd = BenchmarkDef(id="test", prompt="do something", checks=[])
        assert bd.weight == 1.0

    def test_weight_validation(self) -> None:
        with pytest.raises(ValidationError):
            BenchmarkDef(id="test", prompt="x", checks=[], weight=-1.0)


class TestBenchmarkSuite:
    def test_defaults(self) -> None:
        suite = BenchmarkSuite(benchmarks=[])
        assert suite.version == 1

    def test_with_benchmarks(self) -> None:
        bd = BenchmarkDef(
            id="test",
            prompt="do it",
            checks=[BenchmarkCheck(type=CheckType.PATTERN_PRESENT, pattern="hello")],
        )
        suite = BenchmarkSuite(benchmarks=[bd])
        assert len(suite.benchmarks) == 1


class TestCheckResult:
    def test_basic(self) -> None:
        cr = CheckResult(type=CheckType.PATTERN_PRESENT, passed=True)
        assert cr.message is None
        assert cr.score is None

    def test_with_score(self) -> None:
        cr = CheckResult(type=CheckType.LLM_JUDGE, passed=True, score=0.9)
        assert cr.score == 0.9


class TestBenchmarkResult:
    def test_basic(self) -> None:
        br = BenchmarkResult(benchmark_id="test", score=0.75, checks=[])
        assert br.output is None

    def test_score_bounds(self) -> None:
        with pytest.raises(ValidationError):
            BenchmarkResult(benchmark_id="test", score=1.5, checks=[])
        with pytest.raises(ValidationError):
            BenchmarkResult(benchmark_id="test", score=-0.1, checks=[])


class TestRunRecord:
    def test_basic(self) -> None:
        rr = RunRecord(
            run_id="abc123",
            timestamp="2026-03-01T00:00:00Z",
            model="test-model",
            score=0.85,
            delta=0.0,
            severity=DriftSeverity.STABLE,
            results=[],
        )
        assert rr.run_id == "abc123"
        assert rr.severity == DriftSeverity.STABLE

    def test_serialization(self) -> None:
        rr = RunRecord(
            run_id="abc123",
            timestamp="2026-03-01T00:00:00Z",
            model="test-model",
            score=0.85,
            delta=-0.05,
            severity=DriftSeverity.WARNING,
            results=[
                BenchmarkResult(
                    benchmark_id="test",
                    score=0.85,
                    checks=[CheckResult(type=CheckType.PATTERN_PRESENT, passed=True)],
                )
            ],
        )
        data = rr.model_dump(mode="json")
        restored = RunRecord.model_validate(data)
        assert restored.run_id == "abc123"
        assert len(restored.results) == 1
