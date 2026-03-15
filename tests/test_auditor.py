"""Tests for the CLAUDE.md auditor."""

from __future__ import annotations

from pathlib import Path

from anchormd.analyzers import run_all
from anchormd.generators.auditor import ClaudeMdAuditor
from anchormd.generators.composer import DocumentComposer
from anchormd.models import ForgeConfig
from anchormd.scanner import CodebaseScanner


def _setup(path: Path):
    """Helper: scan + analyze a project, return (structure, analyses, config)."""
    config = ForgeConfig(root_path=path)
    scanner = CodebaseScanner(config)
    structure = scanner.scan()
    analyses = run_all(structure, config)
    return structure, analyses, config


class TestScoring:
    def test_good_claude_md_scores_high(self, tmp_project: Path) -> None:
        structure, analyses, config = _setup(tmp_project)
        # Generate a proper CLAUDE.md first.
        composer = DocumentComposer(config)
        content = composer.compose(structure, analyses)

        auditor = ClaudeMdAuditor(config)
        report = auditor.audit(content, structure, analyses)
        assert report.score >= 60

    def test_empty_claude_md_scores_low(self, tmp_project: Path) -> None:
        structure, analyses, config = _setup(tmp_project)
        auditor = ClaudeMdAuditor(config)
        report = auditor.audit("# CLAUDE.md\n", structure, analyses)
        assert report.score < 40

    def test_score_always_in_range(self, tmp_project: Path) -> None:
        structure, analyses, config = _setup(tmp_project)
        auditor = ClaudeMdAuditor(config)

        for content in ["", "# x\n", "x" * 10000]:
            report = auditor.audit(content, structure, analyses)
            assert 0 <= report.score <= 100


class TestSectionCoverage:
    def test_missing_commands_is_error(self, tmp_project: Path) -> None:
        structure, analyses, config = _setup(tmp_project)
        content = "## Project Overview\nA project.\n\n## Architecture\n```\ntree\n```\n"
        auditor = ClaudeMdAuditor(config)
        report = auditor.audit(content, structure, analyses)
        assert "Common Commands" in report.missing_sections
        error_findings = [f for f in report.findings if f.severity == "error"]
        assert any("Common Commands" in f.message for f in error_findings)

    def test_all_sections_present_no_coverage_errors(self, tmp_project: Path) -> None:
        structure, analyses, config = _setup(tmp_project)
        # Build content with all required sections.
        content = (
            "## Project Overview\nA project.\n\n"
            "## Common Commands\n```bash\npytest\n```\n\n"
            "## Architecture\n```\ntree\n```\n\n"
            "## Coding Standards\n- snake_case\n\n"
            "## Anti-Patterns\n- Do NOT use any\n\n"
            "## Dependencies\n- pytest\n\n"
            "## Git Conventions\n- conventional commits\n\n"
            "## Domain Context\n- models\n\n"
        )
        auditor = ClaudeMdAuditor(config)
        report = auditor.audit(content, structure, analyses)
        coverage_errors = [
            f for f in report.findings if f.category == "coverage" and f.severity == "error"
        ]
        assert len(coverage_errors) == 0


class TestAccuracy:
    def test_greenfield_on_large_project(self, tmp_project: Path) -> None:
        # Create many files to make it a "large" project.
        src = tmp_project / "src" / "myapp"
        for i in range(60):
            (src / f"mod_{i}.py").write_text(f"x = {i}\n")

        structure, analyses, config = _setup(tmp_project)
        content = "## Project Overview\nThis is a greenfield project.\n"
        auditor = ClaudeMdAuditor(config)
        report = auditor.audit(content, structure, analyses)
        assert any("greenfield" in f.message.lower() for f in report.findings)


class TestAntiPatterns:
    def test_too_long(self, tmp_project: Path) -> None:
        structure, analyses, config = _setup(tmp_project)
        content = "line\n" * 600
        auditor = ClaudeMdAuditor(config)
        report = auditor.audit(content, structure, analyses)
        assert any("too long" in f.message.lower() for f in report.findings)

    def test_too_short(self, tmp_project: Path) -> None:
        structure, analyses, config = _setup(tmp_project)
        content = "# CLAUDE.md\n"
        auditor = ClaudeMdAuditor(config)
        report = auditor.audit(content, structure, analyses)
        assert any("too short" in f.message.lower() for f in report.findings)

    def test_todo_detected(self, tmp_project: Path) -> None:
        structure, analyses, config = _setup(tmp_project)
        content = "## Project Overview\nTODO: fill this in\n" * 20
        auditor = ClaudeMdAuditor(config)
        report = auditor.audit(content, structure, analyses)
        assert any("TODO" in f.message for f in report.findings)

    def test_conversation_fragments(self, tmp_project: Path) -> None:
        structure, analyses, config = _setup(tmp_project)
        content = "## Project\nCan you help me write a good CLAUDE.md?\n" * 20
        auditor = ClaudeMdAuditor(config)
        report = auditor.audit(content, structure, analyses)
        assert any("conversation" in f.message.lower() for f in report.findings)


class TestSpecificity:
    def test_vague_best_practices(self, tmp_project: Path) -> None:
        structure, analyses, config = _setup(tmp_project)
        content = (
            "## Project Overview\nA project.\n\n## Coding Standards\nFollow best practices.\n" * 10
        )
        auditor = ClaudeMdAuditor(config)
        report = auditor.audit(content, structure, analyses)
        assert any(
            "vague" in f.message.lower() or "follow best practices" in f.message.lower()
            for f in report.findings
        )


class TestFreshness:
    def test_stale_file_reference(self, tmp_project: Path) -> None:
        structure, analyses, config = _setup(tmp_project)
        content = "## Architecture\nMain code in `src/nonexistent/module.py`.\n" * 20
        auditor = ClaudeMdAuditor(config)
        report = auditor.audit(content, structure, analyses)
        freshness = [f for f in report.findings if f.category == "freshness"]
        assert len(freshness) > 0
