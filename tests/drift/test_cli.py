"""Tests for drift CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from anchormd.cli import app
from anchormd.drift.models import (
    BenchmarkResult,
    CheckResult,
    CheckType,
    DriftSeverity,
    RunRecord,
)
from anchormd.drift.storage import ensure_dirs, save_run

runner = CliRunner()

# Patch targets at the source module, not the lazy-import site.
_LICENSING = "anchormd.licensing._find_license_key"
_ADAPTERS = "anchormd.drift.adapters.get_adapter"


def _mock_free_license():
    return patch(_LICENSING, return_value=None)


def _mock_pro_license():
    from anchormd.licensing import LicenseInfo, Tier

    return patch.multiple(
        "anchormd.licensing",
        _find_license_key=MagicMock(return_value="ANMD-ABCD-EFGH-32E3"),
        _validate_with_server=MagicMock(
            return_value=LicenseInfo(
                tier=Tier.PRO,
                license_key="ANMD-ABCD-EFGH-32E3",
                valid=True,
            )
        ),
    )


def _make_run_record(score: float = 0.85) -> RunRecord:
    return RunRecord(
        run_id="cli_test",
        timestamp="2026-03-01T12:00:00Z",
        model="test-model",
        score=score,
        delta=0.0,
        severity=DriftSeverity.STABLE,
        results=[
            BenchmarkResult(
                benchmark_id="test",
                score=score,
                checks=[CheckResult(type=CheckType.PATTERN_PRESENT, passed=True)],
            )
        ],
    )


def _seed_history(root: Path, records: list[RunRecord]) -> None:
    """Write run records to the history dir so load_history finds them."""
    ensure_dirs(root)
    for r in records:
        save_run(root, r)


class TestDriftInit:
    def test_creates_benchmark_file(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["drift", "init", str(tmp_path)])
        assert result.exit_code == 0
        assert (tmp_path / ".anchormd" / "benchmarks" / "default.yaml").exists()
        assert "benchmarks ready" in result.output

    def test_idempotent(self, tmp_path: Path) -> None:
        runner.invoke(app, ["drift", "init", str(tmp_path)])
        result = runner.invoke(app, ["drift", "init", str(tmp_path)])
        assert "already exists" in result.output


class TestDriftRun:
    def test_no_benchmarks(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["drift", "run", str(tmp_path), "--model", "ollama/test"])
        assert result.exit_code == 1
        assert "No benchmarks" in result.output

    def test_run_success(self, tmp_path: Path) -> None:
        runner.invoke(app, ["drift", "init", str(tmp_path)])

        mock_adapter = MagicMock()
        mock_adapter.complete.return_value = "def hello_world():\n    pass"
        mock_adapter.name.return_value = "test-model"

        with patch(_ADAPTERS, return_value=mock_adapter):
            result = runner.invoke(app, ["drift", "run", str(tmp_path), "--model", "ollama/test"])
        assert result.exit_code == 0
        history_dir = tmp_path / ".anchormd" / "drift" / "history"
        assert list(history_dir.glob("*.json"))


class TestDriftReport:
    def test_no_history(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["drift", "report", str(tmp_path)])
        assert result.exit_code == 1
        assert "No run history" in result.output

    def test_terminal_report(self, tmp_path: Path) -> None:
        _seed_history(tmp_path, [_make_run_record()])
        result = runner.invoke(app, ["drift", "report", str(tmp_path)])
        assert result.exit_code == 0

    def test_json_report(self, tmp_path: Path) -> None:
        _seed_history(tmp_path, [_make_run_record()])
        result = runner.invoke(app, ["drift", "report", str(tmp_path), "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["score"] == 0.85

    def test_ci_mode_critical(self, tmp_path: Path) -> None:
        critical_run = _make_run_record(score=0.3)
        critical_run.severity = DriftSeverity.CRITICAL
        critical_run.delta = -0.5
        _seed_history(tmp_path, [critical_run])

        with _mock_pro_license():
            result = runner.invoke(app, ["drift", "report", str(tmp_path), "--ci"])
        assert result.exit_code == 1

    def test_ci_mode_stable(self, tmp_path: Path) -> None:
        _seed_history(tmp_path, [_make_run_record()])
        with _mock_pro_license():
            result = runner.invoke(app, ["drift", "report", str(tmp_path), "--ci"])
        assert result.exit_code == 0

    def test_ci_mode_free_tier(self, tmp_path: Path) -> None:
        _seed_history(tmp_path, [_make_run_record()])
        with _mock_free_license():
            result = runner.invoke(app, ["drift", "report", str(tmp_path), "--ci"])
        assert result.exit_code == 1
        assert "Pro tier" in result.output

    def test_html_report_free_tier(self, tmp_path: Path) -> None:
        _seed_history(tmp_path, [_make_run_record()])
        with _mock_free_license():
            result = runner.invoke(
                app,
                ["drift", "report", str(tmp_path), "--html", str(tmp_path / "report.html")],
            )
        assert result.exit_code == 1
        assert "Pro tier" in result.output


class TestDriftBaseline:
    def test_no_history(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["drift", "baseline", str(tmp_path)])
        assert result.exit_code == 1
        assert "No run history" in result.output

    def test_set_baseline(self, tmp_path: Path) -> None:
        _seed_history(tmp_path, [_make_run_record()])
        result = runner.invoke(app, ["drift", "baseline", str(tmp_path)])
        assert result.exit_code == 0
        assert "Baseline set" in result.output
        assert (tmp_path / ".anchormd" / "drift" / "baseline.json").exists()


class TestDriftTrend:
    def test_empty_history(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["drift", "trend", str(tmp_path)])
        assert "No run history" in result.output

    def test_with_history(self, tmp_path: Path) -> None:
        r1 = _make_run_record(score=0.7)
        r1.run_id = "run1"
        r1.timestamp = "2026-03-01T10:00:00Z"
        r2 = _make_run_record(score=0.9)
        r2.run_id = "run2"
        r2.timestamp = "2026-03-02T10:00:00Z"
        _seed_history(tmp_path, [r1, r2])
        result = runner.invoke(app, ["drift", "trend", str(tmp_path)])
        assert "Score Trend" in result.output


class TestDriftGenerate:
    def test_free_tier_blocked(self, tmp_path: Path) -> None:
        with _mock_free_license():
            result = runner.invoke(
                app,
                ["drift", "generate", str(tmp_path), "--model", "ollama/test"],
            )
        assert result.exit_code == 1

    def test_pro_tier_no_file(self, tmp_path: Path) -> None:
        with _mock_pro_license():
            result = runner.invoke(
                app,
                [
                    "drift",
                    "generate",
                    str(tmp_path),
                    "--from",
                    "CLAUDE.md",
                    "--model",
                    "ollama/test",
                ],
            )
        assert result.exit_code == 1
        assert "not found" in result.output


class TestDriftFix:
    def test_free_tier_blocked(self, tmp_path: Path) -> None:
        with _mock_free_license():
            result = runner.invoke(app, ["drift", "fix", str(tmp_path), "--model", "ollama/test"])
        assert result.exit_code == 1

    def test_pro_no_history(self, tmp_path: Path) -> None:
        with _mock_pro_license():
            result = runner.invoke(app, ["drift", "fix", str(tmp_path), "--model", "ollama/test"])
        assert result.exit_code == 1
        assert "No run history" in result.output
