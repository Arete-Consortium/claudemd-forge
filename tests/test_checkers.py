"""Tests for individual audit checker modules."""

from __future__ import annotations

from pathlib import Path

from claudemd_forge.generators.checkers import (
    AccuracyChecker,
    AntiPatternChecker,
    CoverageChecker,
    FreshnessChecker,
    SpecificityChecker,
)
from claudemd_forge.models import AnalysisResult, FileInfo, ProjectStructure


class TestCoverageChecker:
    def test_all_sections_present(self) -> None:
        content = (
            "## Project Overview\n"
            "## Common Commands\n"
            "## Architecture\n"
            "## Coding Standards\n"
            "## Anti-Patterns\n"
            "## Dependencies\n"
            "## Git Conventions\n"
            "## Domain Context\n"
        )
        checker = CoverageChecker()
        findings = checker.check(content)
        assert len(findings) == 0

    def test_missing_critical_section(self) -> None:
        checker = CoverageChecker()
        findings = checker.check("## Coding Standards\nSome content.\n")
        errors = [f for f in findings if f.severity == "error"]
        assert len(errors) > 0
        messages = " ".join(f.message for f in errors)
        assert "Common Commands" in messages

    def test_case_insensitive_match(self) -> None:
        content = "## project overview\nSome content.\n"
        checker = CoverageChecker()
        findings = checker.check(content)
        overview_findings = [f for f in findings if "Project Overview" in f.message]
        assert len(overview_findings) == 0


class TestAccuracyChecker:
    def test_greenfield_large_project(self) -> None:
        checker = AccuracyChecker()
        structure = ProjectStructure(
            root=Path("/tmp"),
            files=[
                FileInfo(
                    path=Path(f"f{i}.py"),
                    extension=".py",
                    size_bytes=100,
                    line_count=10,
                )
                for i in range(60)
            ],
            directories=[],
            total_files=60,
            total_lines=600,
        )
        findings = checker.check("This is a greenfield project.", structure, [])
        assert any("greenfield" in f.message.lower() for f in findings)

    def test_no_greenfield_on_small_project(self) -> None:
        checker = AccuracyChecker()
        structure = ProjectStructure(
            root=Path("/tmp"),
            files=[],
            directories=[],
            total_files=5,
            total_lines=100,
        )
        findings = checker.check("This is a greenfield project.", structure, [])
        assert len(findings) == 0

    def test_framework_mismatch(self) -> None:
        checker = AccuracyChecker()
        structure = ProjectStructure(
            root=Path("/tmp"),
            files=[],
            directories=[],
            total_files=10,
            total_lines=100,
        )
        analysis = AnalysisResult(
            category="language",
            findings={"frameworks": ["fastapi"]},
            confidence=0.9,
            section_content="",
        )
        findings = checker.check("We use django for the backend.", structure, [analysis])
        assert any("django" in f.message for f in findings)


class TestAntiPatternChecker:
    def test_too_long(self) -> None:
        checker = AntiPatternChecker()
        findings = checker.check("line\n" * 600)
        assert any("too long" in f.message.lower() for f in findings)

    def test_too_short(self) -> None:
        checker = AntiPatternChecker()
        findings = checker.check("# Title\n")
        assert any("too short" in f.message.lower() for f in findings)

    def test_todo_detected(self) -> None:
        checker = AntiPatternChecker()
        findings = checker.check("## Overview\nTODO: fill this in\n")
        assert any("TODO" in f.message for f in findings)

    def test_conversation_fragments(self) -> None:
        checker = AntiPatternChecker()
        findings = checker.check("Can you help me with this project?\n" * 20)
        assert any("conversation" in f.message.lower() for f in findings)

    def test_first_person(self) -> None:
        checker = AntiPatternChecker()
        findings = checker.check("We use pytest for testing.\n" * 20)
        assert any("first-person" in f.message.lower() for f in findings)

    def test_unclosed_code_block(self) -> None:
        checker = AntiPatternChecker()
        findings = checker.check("```python\ncode here\n")
        assert any("unclosed" in f.message.lower() for f in findings)

    def test_normal_content_no_issues(self) -> None:
        checker = AntiPatternChecker()
        content = "\n".join([f"Line {i}: normal content here." for i in range(25)])
        findings = checker.check(content)
        assert len(findings) == 0


class TestSpecificityChecker:
    def test_vague_phrase_detected(self) -> None:
        checker = SpecificityChecker()
        findings = checker.check("Follow best practices for coding.\n")
        assert any("vague" in f.message.lower() for f in findings)

    def test_anti_patterns_without_code(self) -> None:
        checker = SpecificityChecker()
        content = "## Anti-Patterns\n- Don't do bad things\n- Avoid mistakes\n"
        findings = checker.check(content)
        assert any("code examples" in f.message.lower() for f in findings)

    def test_commands_without_code_block(self) -> None:
        checker = SpecificityChecker()
        content = "## Common Commands\nRun the tests and then lint.\n"
        findings = checker.check(content)
        assert any("command" in f.message.lower() for f in findings)


class TestFreshnessChecker:
    def test_stale_path_reference(self) -> None:
        checker = FreshnessChecker()
        structure = ProjectStructure(
            root=Path("/tmp"),
            files=[
                FileInfo(
                    path=Path("src/app.py"),
                    extension=".py",
                    size_bytes=100,
                    line_count=10,
                )
            ],
            directories=[Path("src")],
            total_files=1,
            total_lines=10,
        )
        content = "Main code in `src/nonexistent/module.py`.\n"
        findings = checker.check(content, structure)
        assert any("nonexistent" in f.message for f in findings)

    def test_valid_path_no_finding(self) -> None:
        checker = FreshnessChecker()
        structure = ProjectStructure(
            root=Path("/tmp"),
            files=[
                FileInfo(
                    path=Path("src/app.py"),
                    extension=".py",
                    size_bytes=100,
                    line_count=10,
                )
            ],
            directories=[Path("src")],
            total_files=1,
            total_lines=10,
        )
        content = "Main code in `src/app.py`.\n"
        findings = checker.check(content, structure)
        assert len(findings) == 0
