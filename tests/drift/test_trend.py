"""Tests for drift trend visualization."""

from __future__ import annotations

from anchormd.drift.models import DriftSeverity, RunRecord
from anchormd.drift.trend import aggregate_trend, render_ascii_trend


def _make_run(run_id: str, score: float, delta: float = 0.0, severity: str = "stable") -> RunRecord:
    return RunRecord(
        run_id=run_id,
        timestamp=f"2026-03-{int(run_id):02d}T12:00:00Z",
        model="test-model",
        score=score,
        delta=delta,
        severity=DriftSeverity(severity),
        results=[],
    )


class TestAggregateTrend:
    def test_basic(self) -> None:
        history = [_make_run("1", 0.8), _make_run("2", 0.9)]
        trend = aggregate_trend(history)
        assert len(trend) == 2
        assert trend[0]["score"] == 0.8
        assert trend[1]["score"] == 0.9

    def test_empty(self) -> None:
        assert aggregate_trend([]) == []

    def test_fields(self) -> None:
        history = [_make_run("1", 0.8, delta=-0.05, severity="warning")]
        trend = aggregate_trend(history)
        assert trend[0]["run_id"] == "1"
        assert trend[0]["delta"] == -0.05
        assert trend[0]["severity"] == "warning"


class TestRenderAsciiTrend:
    def test_empty(self) -> None:
        result = render_ascii_trend([])
        assert "No run history" in result

    def test_single_run(self) -> None:
        history = [_make_run("1", 0.85)]
        result = render_ascii_trend(history)
        assert "0.85" in result
        assert "Score Trend" in result

    def test_multiple_runs(self) -> None:
        history = [
            _make_run("1", 0.7, delta=0.0, severity="stable"),
            _make_run("2", 0.8, delta=0.1, severity="improved"),
            _make_run("3", 0.6, delta=-0.2, severity="critical"),
        ]
        result = render_ascii_trend(history)
        assert "Runs: 3" in result
        assert "Best: 0.80" in result
        assert "Worst: 0.60" in result

    def test_severity_indicators(self) -> None:
        history = [
            _make_run("1", 0.5, delta=-0.2, severity="critical"),
            _make_run("2", 0.6, delta=-0.1, severity="warning"),
            _make_run("3", 0.7, delta=0.0, severity="stable"),
            _make_run("4", 0.9, delta=0.1, severity="improved"),
        ]
        result = render_ascii_trend(history)
        assert "!" in result  # critical
        assert "~" in result  # warning
        assert "+" in result  # improved

    def test_custom_width(self) -> None:
        history = [_make_run("1", 0.5)]
        result = render_ascii_trend(history, width=30)
        assert len(result) > 0  # Just check it doesn't crash.
