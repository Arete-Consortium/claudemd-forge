"""Tests for drift reporter."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from rich.console import Console

from anchormd.drift.models import (
    BenchmarkResult,
    CheckResult,
    CheckType,
    DriftSeverity,
    RunRecord,
)
from anchormd.drift.reporter import (
    render_html_report,
    render_json_report,
    render_terminal_report,
)


def _make_run(
    severity: DriftSeverity = DriftSeverity.STABLE,
    score: float = 0.85,
    delta: float = 0.0,
) -> RunRecord:
    return RunRecord(
        run_id="rpt_test",
        timestamp="2026-03-01T12:00:00Z",
        model="test-model",
        score=score,
        delta=delta,
        severity=severity,
        results=[
            BenchmarkResult(
                benchmark_id="test_bench",
                score=score,
                checks=[
                    CheckResult(type=CheckType.PATTERN_PRESENT, passed=True, message="Found"),
                    CheckResult(type=CheckType.PATTERN_ABSENT, passed=False, message="Present"),
                ],
            )
        ],
    )


class TestTerminalReport:
    def test_renders_without_error(self) -> None:
        console = Console(file=MagicMock(), no_color=True)
        run = _make_run()
        render_terminal_report(run, console=console)

    def test_with_baseline(self) -> None:
        console = Console(file=MagicMock(), no_color=True)
        run = _make_run(delta=-0.1, severity=DriftSeverity.WARNING)
        baseline = _make_run(score=0.95)
        render_terminal_report(run, baseline=baseline, console=console)

    def test_critical_severity(self) -> None:
        console = Console(file=MagicMock(), no_color=True)
        run = _make_run(delta=-0.2, severity=DriftSeverity.CRITICAL, score=0.5)
        render_terminal_report(run, console=console)

    def test_no_results(self) -> None:
        console = Console(file=MagicMock(), no_color=True)
        run = RunRecord(
            run_id="empty",
            timestamp="2026-03-01T12:00:00Z",
            model="test",
            score=0.0,
            delta=0.0,
            severity=DriftSeverity.STABLE,
            results=[],
        )
        render_terminal_report(run, console=console)

    def test_default_console(self) -> None:
        run = _make_run()
        # Should not raise with default console.
        render_terminal_report(run)


class TestJsonReport:
    def test_valid_json(self) -> None:
        run = _make_run()
        output = render_json_report(run)
        data = json.loads(output)
        assert data["run_id"] == "rpt_test"
        assert data["score"] == 0.85
        assert data["severity"] == "stable"

    def test_results_included(self) -> None:
        run = _make_run()
        data = json.loads(render_json_report(run))
        assert len(data["results"]) == 1
        assert len(data["results"][0]["checks"]) == 2

    def test_all_severities(self) -> None:
        for severity in DriftSeverity:
            run = _make_run(severity=severity)
            data = json.loads(render_json_report(run))
            assert data["severity"] == str(severity)


class TestHtmlReport:
    def test_renders_html(self) -> None:
        history = [
            _make_run(score=0.7, delta=0.0),
            _make_run(score=0.8, delta=0.1),
        ]
        html = render_html_report(history)
        assert "<!DOCTYPE html>" in html
        assert "Chart" in html
        assert "test-model" in html

    def test_empty_history(self) -> None:
        html = render_html_report([])
        assert "<!DOCTYPE html>" in html

    def test_all_severities_in_table(self) -> None:
        history = [
            _make_run(severity=DriftSeverity.CRITICAL, score=0.3, delta=-0.3),
            _make_run(severity=DriftSeverity.WARNING, score=0.6, delta=-0.1),
            _make_run(severity=DriftSeverity.STABLE, score=0.8, delta=0.0),
            _make_run(severity=DriftSeverity.IMPROVED, score=0.95, delta=0.1),
        ]
        html = render_html_report(history)
        assert "CRITICAL" in html
        assert "WARNING" in html
        assert "STABLE" in html
        assert "IMPROVED" in html
