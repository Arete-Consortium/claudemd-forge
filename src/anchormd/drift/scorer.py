"""Scoring and severity classification for drift runs."""

from __future__ import annotations

from anchormd.drift.models import (
    BenchmarkDef,
    BenchmarkResult,
    DriftSeverity,
)

# Thresholds for delta classification (from spec).
DRIFT_THRESHOLDS: dict[str, float] = {
    "critical": -0.15,
    "warning": -0.05,
    "improved": 0.05,
}


def score_benchmark(result: BenchmarkResult) -> float:
    """Compute score as fraction of checks passed."""
    if not result.checks:
        return 1.0
    passed = sum(1 for c in result.checks if c.passed)
    return passed / len(result.checks)


def score_run(results: list[BenchmarkResult], benchmarks: list[BenchmarkDef]) -> float:
    """Compute weighted average score across all benchmarks."""
    if not results:
        return 0.0

    weight_map = {b.id: b.weight for b in benchmarks}
    total_weight = 0.0
    weighted_sum = 0.0

    for r in results:
        w = weight_map.get(r.benchmark_id, 1.0)
        weighted_sum += r.score * w
        total_weight += w

    if total_weight == 0.0:
        return 0.0
    return weighted_sum / total_weight


def compute_delta(current: float, baseline: float | None) -> float:
    """Compute score delta from baseline. Returns 0.0 if no baseline."""
    if baseline is None:
        return 0.0
    return current - baseline


def classify_severity(delta: float) -> DriftSeverity:
    """Classify drift severity based on delta thresholds."""
    if delta <= DRIFT_THRESHOLDS["critical"]:
        return DriftSeverity.CRITICAL
    if delta <= DRIFT_THRESHOLDS["warning"]:
        return DriftSeverity.WARNING
    if delta >= DRIFT_THRESHOLDS["improved"]:
        return DriftSeverity.IMPROVED
    return DriftSeverity.STABLE
