"""Tests for the reality verifier."""

from __future__ import annotations

from pathlib import Path

import pytest

from anchormd.analyzers.reality import verify


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "1.2.3"\n'
        'dependencies = ["typer>=0.9", "rich"]\n'
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("# app")
    return tmp_path


def test_verify_passes_on_matching_claims(project: Path) -> None:
    content = (
        "# demo\n\n## Current State\n"
        "- **Version**: 1.2.3\n\n"
        "## Architecture\n```\n"
        "demo/\n├── src/app.py\n```\n\n"
        "## Dependencies\n- typer\n- rich\n"
    )
    report = verify(content, project)
    assert report.score == 100
    assert not report.findings


def test_verify_detects_version_mismatch(project: Path) -> None:
    content = "## Current State\n- **Version**: 9.9.9\n"
    report = verify(content, project)
    categories = {f.category for f in report.findings}
    assert "version_mismatch" in categories


def test_verify_detects_missing_file(project: Path) -> None:
    content = "## Architecture\n```\nsrc/missing.py\n```\n"
    report = verify(content, project)
    assert any(f.category == "missing_file" for f in report.findings)


def test_verify_detects_unknown_dep(project: Path) -> None:
    content = (
        "## Dependencies\n- typer\n- fakepackage\n"
    )
    report = verify(content, project)
    assert any(
        f.category == "unknown_dep" and "fakepackage" in f.claim for f in report.findings
    )


def test_verify_empty_claims(tmp_path: Path) -> None:
    report = verify("# Empty\n\nNo claims.\n", tmp_path)
    assert report.checks_run == 0
    assert report.score == 0
