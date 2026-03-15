"""Tests for drift storage layer."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

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
from anchormd.drift.storage import (
    ensure_dirs,
    load_baseline,
    load_benchmarks,
    load_history,
    load_trend,
    save_baseline,
    save_benchmarks,
    save_run,
    save_trend,
)
from anchormd.exceptions import DriftError


@pytest.fixture
def drift_root(tmp_path: Path) -> Path:
    """Return a temp path with drift dirs created."""
    ensure_dirs(tmp_path)
    return tmp_path


def _make_suite() -> BenchmarkSuite:
    return BenchmarkSuite(
        benchmarks=[
            BenchmarkDef(
                id="test_bench",
                prompt="Write hello world",
                checks=[
                    BenchmarkCheck(type=CheckType.PATTERN_PRESENT, pattern="hello"),
                ],
            )
        ]
    )


def _make_record(run_id: str = "abc123", score: float = 0.85) -> RunRecord:
    return RunRecord(
        run_id=run_id,
        timestamp="2026-03-01T12:00:00Z",
        model="test-model",
        score=score,
        delta=0.0,
        severity=DriftSeverity.STABLE,
        results=[
            BenchmarkResult(
                benchmark_id="test_bench",
                score=score,
                checks=[
                    CheckResult(type=CheckType.PATTERN_PRESENT, passed=True),
                ],
                output="hello world",
            )
        ],
    )


class TestEnsureDirs:
    def test_creates_directories(self, tmp_path: Path) -> None:
        ensure_dirs(tmp_path)
        assert (tmp_path / ".anchormd" / "benchmarks").is_dir()
        assert (tmp_path / ".anchormd" / "drift" / "history").is_dir()

    def test_idempotent(self, drift_root: Path) -> None:
        ensure_dirs(drift_root)  # Should not raise.
        assert (drift_root / ".anchormd" / "benchmarks").is_dir()


class TestBenchmarks:
    def test_save_and_load(self, drift_root: Path) -> None:
        suite = _make_suite()
        save_benchmarks(drift_root, suite, "test.yaml")
        loaded = load_benchmarks(drift_root)
        assert len(loaded) == 1
        assert loaded[0].benchmarks[0].id == "test_bench"

    def test_load_empty(self, drift_root: Path) -> None:
        loaded = load_benchmarks(drift_root)
        assert loaded == []

    def test_load_no_dir(self, tmp_path: Path) -> None:
        loaded = load_benchmarks(tmp_path)
        assert loaded == []

    def test_save_auto_yaml_extension(self, drift_root: Path) -> None:
        suite = _make_suite()
        save_benchmarks(drift_root, suite, "no_ext")
        assert (drift_root / ".anchormd" / "benchmarks" / "no_ext.yaml").exists()

    def test_load_invalid_yaml(self, drift_root: Path) -> None:
        bad_file = drift_root / ".anchormd" / "benchmarks" / "bad.yaml"
        bad_file.write_text(": invalid: yaml: {{")
        with pytest.raises(DriftError, match="Failed to parse"):
            load_benchmarks(drift_root)

    def test_load_invalid_schema(self, drift_root: Path) -> None:
        bad_file = drift_root / ".anchormd" / "benchmarks" / "bad.yaml"
        bad_file.write_text(yaml.dump({"version": 1, "benchmarks": [{"id": 123}]}))
        with pytest.raises(DriftError, match="Failed to parse"):
            load_benchmarks(drift_root)

    def test_load_skips_empty_yaml(self, drift_root: Path) -> None:
        (drift_root / ".anchormd" / "benchmarks" / "empty.yaml").write_text("")
        loaded = load_benchmarks(drift_root)
        assert loaded == []

    def test_multiple_suites(self, drift_root: Path) -> None:
        suite = _make_suite()
        save_benchmarks(drift_root, suite, "a.yaml")
        save_benchmarks(drift_root, suite, "b.yaml")
        loaded = load_benchmarks(drift_root)
        assert len(loaded) == 2


class TestBaseline:
    def test_save_and_load(self, drift_root: Path) -> None:
        record = _make_record()
        save_baseline(drift_root, record)
        loaded = load_baseline(drift_root)
        assert loaded is not None
        assert loaded.run_id == "abc123"

    def test_load_missing(self, drift_root: Path) -> None:
        assert load_baseline(drift_root) is None

    def test_load_corrupt(self, drift_root: Path) -> None:
        path = drift_root / ".anchormd" / "drift" / "baseline.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json")
        assert load_baseline(drift_root) is None


class TestRunHistory:
    def test_save_and_load(self, drift_root: Path) -> None:
        record = _make_record()
        save_run(drift_root, record)
        history = load_history(drift_root)
        assert len(history) == 1
        assert history[0].run_id == "abc123"

    def test_output_stripped_on_save(self, drift_root: Path) -> None:
        record = _make_record()
        save_run(drift_root, record)
        history = load_history(drift_root)
        assert history[0].results[0].output is None

    def test_load_empty(self, drift_root: Path) -> None:
        assert load_history(drift_root) == []

    def test_load_no_dir(self, tmp_path: Path) -> None:
        assert load_history(tmp_path) == []

    def test_multiple_runs_sorted(self, drift_root: Path) -> None:
        r1 = _make_record(run_id="first", score=0.7)
        r1.timestamp = "2026-03-01T10:00:00Z"
        r2 = _make_record(run_id="second", score=0.9)
        r2.timestamp = "2026-03-02T10:00:00Z"
        save_run(drift_root, r2)
        save_run(drift_root, r1)
        history = load_history(drift_root)
        assert len(history) == 2
        assert history[0].run_id == "first"
        assert history[1].run_id == "second"

    def test_skips_corrupt_files(self, drift_root: Path) -> None:
        record = _make_record()
        save_run(drift_root, record)
        bad = drift_root / ".anchormd" / "drift" / "history" / "2026-03-01_badfile.json"
        bad.write_text("not json")
        history = load_history(drift_root)
        assert len(history) == 1


class TestTrend:
    def test_save_and_load(self, drift_root: Path) -> None:
        data = [{"score": 0.85, "date": "2026-03-01"}]
        save_trend(drift_root, data)
        loaded = load_trend(drift_root)
        assert loaded == data

    def test_load_missing(self, drift_root: Path) -> None:
        assert load_trend(drift_root) == []

    def test_load_corrupt(self, drift_root: Path) -> None:
        path = drift_root / ".anchormd" / "drift" / "trend.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json")
        assert load_trend(drift_root) == []

    def test_load_non_list(self, drift_root: Path) -> None:
        path = drift_root / ".anchormd" / "drift" / "trend.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"not": "a list"}')
        assert load_trend(drift_root) == []
