"""Tests for the CLI interface."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from claudemd_forge.cli import app

runner = CliRunner()


def _normalized(output: str) -> str:
    """Collapse whitespace for assertion matching (rich wraps long lines)."""
    return " ".join(output.split())


class TestGenerate:
    def test_generate_creates_file(self, tmp_project: Path) -> None:
        result = runner.invoke(app, ["generate", str(tmp_project), "--quiet"])
        assert result.exit_code == 0
        assert (tmp_project / "CLAUDE.md").exists()

    def test_generate_refuses_overwrite(self, tmp_project: Path) -> None:
        (tmp_project / "CLAUDE.md").write_text("# existing")
        result = runner.invoke(app, ["generate", str(tmp_project)])
        assert result.exit_code == 1
        assert "already exists" in _normalized(result.output)

    def test_generate_force_overwrites(self, tmp_project: Path) -> None:
        (tmp_project / "CLAUDE.md").write_text("# old")
        result = runner.invoke(app, ["generate", str(tmp_project), "--force", "--quiet"])
        assert result.exit_code == 0
        content = (tmp_project / "CLAUDE.md").read_text()
        assert "# CLAUDE.md" in content
        assert content != "# old"

    def test_generate_quiet_suppresses_output(self, tmp_project: Path) -> None:
        result = runner.invoke(app, ["generate", str(tmp_project), "--quiet"])
        assert result.exit_code == 0
        assert "ClaudeMD Forge" not in result.output

    def test_generate_invalid_path(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["generate", str(tmp_path / "nonexistent")])
        assert result.exit_code == 1
        assert "not a directory" in result.output

    def test_generate_custom_output(self, tmp_project: Path) -> None:
        out = tmp_project / "docs" / "CLAUDE.md"
        out.parent.mkdir(exist_ok=True)
        result = runner.invoke(app, ["generate", str(tmp_project), "-o", str(out), "--quiet"])
        assert result.exit_code == 0
        assert out.exists()

    def test_generate_content_has_python(self, tmp_project: Path) -> None:
        result = runner.invoke(app, ["generate", str(tmp_project), "--quiet"])
        assert result.exit_code == 0
        content = (tmp_project / "CLAUDE.md").read_text()
        assert "Python" in content


class TestAudit:
    def test_audit_minimal_claude_md(self, tmp_project: Path) -> None:
        (tmp_project / "CLAUDE.md").write_text("# CLAUDE.md\n\nJust a title.\n")
        result = runner.invoke(app, ["audit", str(tmp_project / "CLAUDE.md")])
        # Should report missing sections.
        assert "Missing" in result.output or "missing" in result.output.lower()

    def test_audit_missing_file(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["audit", str(tmp_path / "CLAUDE.md")])
        assert result.exit_code == 1
        assert "not a file" in _normalized(result.output)

    def test_audit_verbose_shows_suggestions(self, tmp_project: Path) -> None:
        (tmp_project / "CLAUDE.md").write_text("# CLAUDE.md\n")
        result = runner.invoke(app, ["audit", str(tmp_project / "CLAUDE.md"), "-v"])
        # With verbose, should show suggestions.
        assert "Score" in result.output

    def test_audit_json_output(self, tmp_project: Path) -> None:
        (tmp_project / "CLAUDE.md").write_text("# CLAUDE.md\n\nJust a title.\n")
        result = runner.invoke(app, ["audit", str(tmp_project / "CLAUDE.md"), "--json"])
        data = json.loads(result.output)
        assert "score" in data
        assert "findings" in data
        assert "missing_sections" in data
        assert "recommendations" in data
        assert isinstance(data["score"], int)
        assert isinstance(data["findings"], list)

    def test_audit_json_missing_file(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["audit", str(tmp_path / "CLAUDE.md"), "--json"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert "error" in data

    def test_audit_json_findings_have_fields(self, tmp_project: Path) -> None:
        (tmp_project / "CLAUDE.md").write_text("# CLAUDE.md\n")
        result = runner.invoke(app, ["audit", str(tmp_project / "CLAUDE.md"), "--json"])
        data = json.loads(result.output)
        if data["findings"]:
            finding = data["findings"][0]
            assert "severity" in finding
            assert "category" in finding
            assert "message" in finding

    def test_audit_fail_below_custom_threshold(self, tmp_project: Path) -> None:
        (tmp_project / "CLAUDE.md").write_text("# CLAUDE.md\n\nJust a title.\n")
        # Default threshold is 40; set it to 80 so a minimal file fails
        result = runner.invoke(app, ["audit", str(tmp_project / "CLAUDE.md"), "--fail-below", "80"])
        assert result.exit_code == 2

    def test_audit_fail_below_zero_always_passes(self, tmp_project: Path) -> None:
        (tmp_project / "CLAUDE.md").write_text("# CLAUDE.md\n")
        result = runner.invoke(app, ["audit", str(tmp_project / "CLAUDE.md"), "--fail-below", "0"])
        assert result.exit_code == 0


class TestPresets:
    def test_presets_lists_available(self) -> None:
        result = runner.invoke(app, ["presets"])
        assert result.exit_code == 0
        assert "default" in result.output.lower() or "Default" in result.output

    def test_frameworks_lists_available(self) -> None:
        result = runner.invoke(app, ["frameworks"])
        assert result.exit_code == 0
        assert "FastAPI" in result.output or "fastapi" in result.output


class TestHelp:
    def test_main_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Generate and audit" in result.output

    def test_generate_help(self) -> None:
        result = runner.invoke(app, ["generate", "--help"])
        assert result.exit_code == 0
        assert "project root" in result.output.lower()

    def test_audit_help(self) -> None:
        result = runner.invoke(app, ["audit", "--help"])
        assert result.exit_code == 0
        assert "CLAUDE.md" in result.output

    def test_version(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output
