"""Storage layer for drift detection data.

Manages benchmark suites, baselines, run history, and trend data
under the `.anchormd/` directory tree.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import yaml
from pydantic import ValidationError

from anchormd.drift.models import BenchmarkSuite, RunRecord
from anchormd.exceptions import DriftError

logger = logging.getLogger(__name__)

_BENCHMARKS_DIR = ".anchormd/benchmarks"
_HISTORY_DIR = ".anchormd/drift/history"
_BASELINE_FILE = ".anchormd/drift/baseline.json"
_TREND_FILE = ".anchormd/drift/trend.json"


def ensure_dirs(root: Path) -> None:
    """Create the drift directory structure under *root*."""
    (root / _BENCHMARKS_DIR).mkdir(parents=True, exist_ok=True)
    (root / _HISTORY_DIR).mkdir(parents=True, exist_ok=True)


def load_benchmarks(root: Path) -> list[BenchmarkSuite]:
    """Load all benchmark suite YAML files from `.anchormd/benchmarks/`."""
    benchmarks_dir = root / _BENCHMARKS_DIR
    if not benchmarks_dir.is_dir():
        return []

    suites: list[BenchmarkSuite] = []
    for yaml_file in sorted(benchmarks_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(yaml_file.read_text())
            if data is None:
                continue
            suite = BenchmarkSuite.model_validate(data)
            suites.append(suite)
        except (yaml.YAMLError, ValidationError) as exc:
            raise DriftError(f"Failed to parse benchmark file {yaml_file.name}: {exc}") from exc

    return suites


def save_benchmarks(root: Path, suite: BenchmarkSuite, filename: str) -> None:
    """Write a benchmark suite to YAML."""
    ensure_dirs(root)
    dest = root / _BENCHMARKS_DIR / filename
    if not dest.name.endswith(".yaml"):
        dest = dest.with_suffix(".yaml")
    data = suite.model_dump(mode="json")
    dest.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))


def load_baseline(root: Path) -> RunRecord | None:
    """Load the saved baseline run record, if it exists."""
    path = root / _BASELINE_FILE
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text())
        return RunRecord.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.warning("Failed to load baseline: %s", exc)
        return None


def save_baseline(root: Path, record: RunRecord) -> None:
    """Persist a run record as the new baseline."""
    ensure_dirs(root)
    path = root / _BASELINE_FILE
    path.write_text(record.model_dump_json(indent=2))


def save_run(root: Path, record: RunRecord) -> None:
    """Save a run record to the history directory."""
    ensure_dirs(root)
    # Strip output from results before persisting to keep history lean.
    stripped = record.model_copy(
        update={
            "results": [r.model_copy(update={"output": None}) for r in record.results],
        }
    )
    date_str = record.timestamp[:10]  # YYYY-MM-DD
    path = root / _HISTORY_DIR / f"{date_str}_{record.run_id[:8]}.json"
    path.write_text(stripped.model_dump_json(indent=2))


def load_history(root: Path) -> list[RunRecord]:
    """Load all run records from history, sorted by timestamp."""
    history_dir = root / _HISTORY_DIR
    if not history_dir.is_dir():
        return []

    records: list[RunRecord] = []
    for json_file in sorted(history_dir.glob("*.json")):
        try:
            data = json.loads(json_file.read_text())
            records.append(RunRecord.model_validate(data))
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning("Skipping corrupt history file %s: %s", json_file.name, exc)

    records.sort(key=lambda r: r.timestamp)
    return records


def load_trend(root: Path) -> list[dict]:
    """Load cached trend data, or return empty list."""
    path = root / _TREND_FILE
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def save_trend(root: Path, trend_data: list[dict]) -> None:
    """Persist aggregated trend data."""
    ensure_dirs(root)
    path = root / _TREND_FILE
    path.write_text(json.dumps(trend_data, indent=2))
