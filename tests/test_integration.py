"""Integration tests for end-to-end CLI workflows."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from claudemd_forge.cli import app

runner = CliRunner()


def _normalized(output: str) -> str:
    """Collapse whitespace for assertion matching."""
    return " ".join(output.split())


class TestGenerateAuditRoundtrip:
    """Generate a CLAUDE.md, then audit it — score should be high."""

    def test_python_project_roundtrip(self, tmp_project: Path) -> None:
        gen = runner.invoke(app, ["generate", str(tmp_project), "--quiet"])
        assert gen.exit_code == 0

        claude_md = tmp_project / "CLAUDE.md"
        assert claude_md.exists()

        content = claude_md.read_text()
        assert "## Project Overview" in content
        assert "## Architecture" in content
        assert "## Common Commands" in content
        assert "## Anti-Patterns" in content
        assert "Python" in content

        audit = runner.invoke(app, ["audit", str(claude_md)])
        assert audit.exit_code == 0
        assert "Score" in audit.output

    def test_react_project_roundtrip(self, tmp_react_project: Path) -> None:
        gen = runner.invoke(app, ["generate", str(tmp_react_project), "--quiet"])
        assert gen.exit_code == 0

        claude_md = tmp_react_project / "CLAUDE.md"
        content = claude_md.read_text()
        assert "TypeScript" in content

        audit = runner.invoke(app, ["audit", str(claude_md)])
        assert audit.exit_code == 0

    def test_empty_project_generates_valid_output(self, tmp_path: Path) -> None:
        gen = runner.invoke(app, ["generate", str(tmp_path), "--quiet"])
        assert gen.exit_code == 0

        claude_md = tmp_path / "CLAUDE.md"
        content = claude_md.read_text()
        assert "# CLAUDE.md" in content
        assert content.endswith("\n")


class TestGenerateWithPreset:
    """Test preset selection during generation."""

    def test_default_preset(self, tmp_project: Path) -> None:
        result = runner.invoke(
            app,
            ["generate", str(tmp_project), "-p", "default", "--quiet"],
        )
        assert result.exit_code == 0

    def test_minimal_preset(self, tmp_project: Path) -> None:
        result = runner.invoke(
            app,
            ["generate", str(tmp_project), "-p", "minimal", "--quiet"],
        )
        assert result.exit_code == 0


class TestGenerateWithOutput:
    """Test custom output paths."""

    def test_output_to_subdirectory(self, tmp_project: Path) -> None:
        docs = tmp_project / "docs"
        docs.mkdir()
        out = docs / "CLAUDE.md"
        result = runner.invoke(
            app,
            ["generate", str(tmp_project), "-o", str(out), "--quiet"],
        )
        assert result.exit_code == 0
        assert out.exists()
        assert "# CLAUDE.md" in out.read_text()

    def test_force_overwrite_preserves_quality(self, tmp_project: Path) -> None:
        claude_md = tmp_project / "CLAUDE.md"
        claude_md.write_text("# old content\n")

        result = runner.invoke(app, ["generate", str(tmp_project), "--force", "--quiet"])
        assert result.exit_code == 0

        content = claude_md.read_text()
        assert "# CLAUDE.md" in content
        assert "old content" not in content


class TestAuditScoring:
    """Verify audit scoring across different content quality levels."""

    def test_generated_scores_higher_than_minimal(self, tmp_project: Path) -> None:
        gen = runner.invoke(app, ["generate", str(tmp_project), "--quiet"])
        assert gen.exit_code == 0

        claude_md = tmp_project / "CLAUDE.md"
        good_audit = runner.invoke(app, ["audit", str(claude_md)])

        claude_md.write_text("# CLAUDE.md\nJust a title.\n")
        bad_audit = runner.invoke(app, ["audit", str(claude_md)])

        good_score = _extract_score(good_audit.output)
        bad_score = _extract_score(bad_audit.output)
        assert good_score > bad_score

    def test_verbose_audit_shows_more_detail(self, tmp_project: Path) -> None:
        claude_md = tmp_project / "CLAUDE.md"
        claude_md.write_text("# CLAUDE.md\nMinimal content.\n")

        normal = runner.invoke(app, ["audit", str(claude_md)])
        verbose = runner.invoke(app, ["audit", str(claude_md), "-v"])

        assert len(verbose.output) >= len(normal.output)


class TestSelfDogfood:
    """Run the tool on its own codebase."""

    def test_generate_on_self(self) -> None:
        root = Path(__file__).parent.parent
        out = root / "test_output_claude.md"
        try:
            result = runner.invoke(
                app,
                ["generate", str(root), "-o", str(out), "--quiet"],
            )
            assert result.exit_code == 0
            content = out.read_text()
            assert "Python" in content
            assert "## Tech Stack" in content
        finally:
            out.unlink(missing_ok=True)

    def test_audit_on_self(self) -> None:
        root = Path(__file__).parent.parent
        claude_md = root / "CLAUDE.md"
        if claude_md.exists():
            result = runner.invoke(app, ["audit", str(claude_md)])
            assert result.exit_code in (0, 2)
            assert "Score" in result.output


def _extract_score(output: str) -> int:
    """Extract numeric score from audit output."""
    import re

    match = re.search(r"Score:\s*(\d+)/100", output)
    if match:
        return int(match.group(1))
    return 0
