"""Tests for drift scorer."""

from __future__ import annotations

from anchormd.drift.models import (
    BenchmarkDef,
    BenchmarkResult,
    CheckResult,
    CheckType,
    DriftSeverity,
)
from anchormd.drift.scorer import (
    DRIFT_THRESHOLDS,
    classify_severity,
    compute_delta,
    score_benchmark,
    score_run,
)


class TestScoreBenchmark:
    def test_all_passed(self) -> None:
        result = BenchmarkResult(
            benchmark_id="test",
            score=0.0,
            checks=[
                CheckResult(type=CheckType.PATTERN_PRESENT, passed=True),
                CheckResult(type=CheckType.PATTERN_ABSENT, passed=True),
            ],
        )
        assert score_benchmark(result) == 1.0

    def test_none_passed(self) -> None:
        result = BenchmarkResult(
            benchmark_id="test",
            score=0.0,
            checks=[
                CheckResult(type=CheckType.PATTERN_PRESENT, passed=False),
                CheckResult(type=CheckType.PATTERN_ABSENT, passed=False),
            ],
        )
        assert score_benchmark(result) == 0.0

    def test_partial(self) -> None:
        result = BenchmarkResult(
            benchmark_id="test",
            score=0.0,
            checks=[
                CheckResult(type=CheckType.PATTERN_PRESENT, passed=True),
                CheckResult(type=CheckType.PATTERN_ABSENT, passed=False),
            ],
        )
        assert score_benchmark(result) == 0.5

    def test_no_checks(self) -> None:
        result = BenchmarkResult(benchmark_id="test", score=0.0, checks=[])
        assert score_benchmark(result) == 1.0


class TestScoreRun:
    def test_weighted_average(self) -> None:
        benchmarks = [
            BenchmarkDef(id="a", prompt="x", checks=[], weight=2.0),
            BenchmarkDef(id="b", prompt="x", checks=[], weight=1.0),
        ]
        results = [
            BenchmarkResult(benchmark_id="a", score=1.0, checks=[]),
            BenchmarkResult(benchmark_id="b", score=0.0, checks=[]),
        ]
        # (1.0*2.0 + 0.0*1.0) / (2.0+1.0) = 0.6667
        score = score_run(results, benchmarks)
        assert abs(score - 2.0 / 3.0) < 0.001

    def test_equal_weights(self) -> None:
        benchmarks = [
            BenchmarkDef(id="a", prompt="x", checks=[]),
            BenchmarkDef(id="b", prompt="x", checks=[]),
        ]
        results = [
            BenchmarkResult(benchmark_id="a", score=0.8, checks=[]),
            BenchmarkResult(benchmark_id="b", score=0.6, checks=[]),
        ]
        assert score_run(results, benchmarks) == 0.7

    def test_empty_results(self) -> None:
        assert score_run([], []) == 0.0

    def test_unknown_benchmark_default_weight(self) -> None:
        results = [BenchmarkResult(benchmark_id="unknown", score=0.5, checks=[])]
        assert score_run(results, []) == 0.5


class TestComputeDelta:
    def test_no_baseline(self) -> None:
        assert compute_delta(0.8, None) == 0.0

    def test_positive_delta(self) -> None:
        assert compute_delta(0.9, 0.8) == pytest.approx(0.1)

    def test_negative_delta(self) -> None:
        assert compute_delta(0.7, 0.9) == pytest.approx(-0.2)

    def test_zero_delta(self) -> None:
        assert compute_delta(0.5, 0.5) == 0.0


class TestClassifySeverity:
    def test_critical(self) -> None:
        assert classify_severity(-0.20) == DriftSeverity.CRITICAL
        assert classify_severity(-0.15) == DriftSeverity.CRITICAL

    def test_warning(self) -> None:
        assert classify_severity(-0.10) == DriftSeverity.WARNING
        assert classify_severity(-0.05) == DriftSeverity.WARNING

    def test_stable(self) -> None:
        assert classify_severity(0.0) == DriftSeverity.STABLE
        assert classify_severity(0.04) == DriftSeverity.STABLE

    def test_improved(self) -> None:
        assert classify_severity(0.05) == DriftSeverity.IMPROVED
        assert classify_severity(0.10) == DriftSeverity.IMPROVED

    def test_thresholds_dict(self) -> None:
        assert "critical" in DRIFT_THRESHOLDS
        assert "warning" in DRIFT_THRESHOLDS
        assert "improved" in DRIFT_THRESHOLDS


# Needed for approx comparison.
import pytest  # noqa: E402
