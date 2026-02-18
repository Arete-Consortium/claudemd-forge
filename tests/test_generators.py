"""Tests for section generators and document composer."""

from __future__ import annotations

from pathlib import Path

from claudemd_forge.analyzers import run_all
from claudemd_forge.generators.composer import DocumentComposer
from claudemd_forge.generators.sections import SectionGenerator
from claudemd_forge.models import AnalysisResult, ForgeConfig, ProjectStructure
from claudemd_forge.scanner import CodebaseScanner


def _full_pipeline(path: Path) -> tuple[ProjectStructure, list[AnalysisResult], ForgeConfig]:
    """Run scanner + analyzers on a path."""
    config = ForgeConfig(root_path=path)
    scanner = CodebaseScanner(config)
    structure = scanner.scan()
    analyses = run_all(structure, config)
    return structure, analyses, config


class TestSectionGenerator:
    def test_generate_header(self) -> None:
        gen = SectionGenerator()
        result = gen.generate_header("MyProject", "A cool project")
        assert "# CLAUDE.md — MyProject" in result
        assert "A cool project" in result

    def test_generate_header_no_description(self) -> None:
        gen = SectionGenerator()
        result = gen.generate_header("MyProject")
        assert "# CLAUDE.md — MyProject" in result

    def test_generate_architecture_has_tree(self, tmp_project: Path) -> None:
        config = ForgeConfig(root_path=tmp_project)
        structure = CodebaseScanner(config).scan()
        gen = SectionGenerator()
        result = gen.generate_architecture(structure)
        assert "```" in result
        assert "## Architecture" in result

    def test_generate_anti_patterns_python(self, tmp_project: Path) -> None:
        structure, analyses, _ = _full_pipeline(tmp_project)
        gen = SectionGenerator()
        result = gen.generate_anti_patterns(structure, analyses)
        assert "## Anti-Patterns" in result
        assert "pathlib" in result.lower() or "os.path" in result.lower()

    def test_generate_anti_patterns_react(self, tmp_react_project: Path) -> None:
        structure, analyses, _ = _full_pipeline(tmp_react_project)
        gen = SectionGenerator()
        result = gen.generate_anti_patterns(structure, analyses)
        assert "class components" in result.lower() or "hooks" in result.lower()

    def test_generate_current_state(self, tmp_project: Path) -> None:
        config = ForgeConfig(root_path=tmp_project)
        structure = CodebaseScanner(config).scan()
        gen = SectionGenerator()
        result = gen.generate_current_state(structure)
        assert "## Current State" in result
        assert "Python" in result

    def test_current_state_uses_structure_version(self, tmp_project: Path) -> None:
        config = ForgeConfig(root_path=tmp_project)
        structure = CodebaseScanner(config).scan()
        # The tmp_project fixture has pyproject.toml with version "0.1.0"
        gen = SectionGenerator()
        result = gen.generate_current_state(structure)
        assert "0.1.0" in result

    def test_current_state_omits_version_when_none(self, tmp_path: Path) -> None:
        config = ForgeConfig(root_path=tmp_path)
        structure = CodebaseScanner(config).scan()
        gen = SectionGenerator()
        result = gen.generate_current_state(structure)
        assert "Version" not in result

    def test_project_overview_uses_structure_description(self) -> None:
        gen = SectionGenerator()
        result = gen.generate_project_overview("MyApp", structure_description="A cool tool")
        assert "A cool tool" in result
        assert "TODO" not in result

    def test_project_overview_explicit_description_wins(self) -> None:
        gen = SectionGenerator()
        result = gen.generate_project_overview(
            "MyApp", description="Explicit", structure_description="Fallback"
        )
        assert "Explicit" in result
        assert "Fallback" not in result

    def test_dependencies_uses_declared_deps(self, tmp_project: Path) -> None:
        config = ForgeConfig(root_path=tmp_project)
        structure = CodebaseScanner(config).scan()
        gen = SectionGenerator()
        result = gen.generate_dependencies([], structure)
        assert "fastapi" in result
        assert "pydantic" in result
        assert "pytest" in result

    def test_dependencies_falls_back_to_analyzer(self) -> None:
        gen = SectionGenerator()
        analysis = AnalysisResult(
            category="language",
            findings={
                "frameworks": ["django"],
                "toolchains": {"test_frameworks": ["pytest"], "linters": []},
            },
            confidence=0.8,
            section_content="",
        )
        structure = ProjectStructure(
            root=Path("/tmp"), files=[], directories=[], total_files=0, total_lines=0
        )
        result = gen.generate_dependencies([analysis], structure)
        assert "django" in result

    def test_architecture_tree_excludes_db_files(self, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text("x = 1\n")
        (tmp_path / "data.db").write_bytes(b"SQLite")
        (tmp_path / "data.db-journal").write_bytes(b"j")
        (tmp_path / "data.db-shm").write_bytes(b"s")
        (tmp_path / "data.db-wal").write_bytes(b"w")
        (tmp_path / ".coverage").write_bytes(b"c")
        (tmp_path / ".env").write_text("SECRET=x\n")
        config = ForgeConfig(root_path=tmp_path)
        structure = CodebaseScanner(config).scan()
        gen = SectionGenerator()
        result = gen.generate_architecture(structure)
        assert "app.py" in result
        assert "data.db" not in result
        assert ".coverage" not in result
        assert ".env" not in result

    def test_generate_git_conventions(self, tmp_project: Path) -> None:
        config = ForgeConfig(root_path=tmp_project)
        structure = CodebaseScanner(config).scan()
        gen = SectionGenerator()
        result = gen.generate_git_conventions(structure)
        assert "Conventional commits" in result


class TestDocumentComposer:
    def test_compose_produces_non_empty(self, tmp_project: Path) -> None:
        structure, analyses, config = _full_pipeline(tmp_project)
        composer = DocumentComposer(config)
        result = composer.compose(structure, analyses)
        assert len(result) > 0
        assert "# CLAUDE.md" in result

    def test_compose_has_expected_sections(self, tmp_project: Path) -> None:
        structure, analyses, config = _full_pipeline(tmp_project)
        composer = DocumentComposer(config)
        result = composer.compose(structure, analyses)
        assert "## Project Overview" in result
        assert "## Current State" in result
        assert "## Architecture" in result
        assert "## Anti-Patterns" in result

    def test_compose_omits_empty_sections(self, tmp_path: Path) -> None:
        """Empty project should still produce valid output."""
        structure, analyses, config = _full_pipeline(tmp_path)
        composer = DocumentComposer(config)
        result = composer.compose(structure, analyses)
        # Should have at least header and some sections.
        assert "# CLAUDE.md" in result

    def test_clean_output_normalizes_blank_lines(self) -> None:
        config = ForgeConfig(root_path=Path("/tmp"))
        composer = DocumentComposer(config)
        result = composer._clean_output("line1\n\n\n\n\nline2\n\n\n")
        assert "\n\n\n" not in result
        assert result.endswith("\n")

    def test_clean_output_single_trailing_newline(self) -> None:
        config = ForgeConfig(root_path=Path("/tmp"))
        composer = DocumentComposer(config)
        result = composer._clean_output("content\n\n\n")
        assert result == "content\n"

    def test_quality_score_range(self, tmp_project: Path) -> None:
        structure, analyses, config = _full_pipeline(tmp_project)
        composer = DocumentComposer(config)
        content = composer.compose(structure, analyses)
        score = composer.estimate_quality_score(content)
        assert 0 <= score <= 100

    def test_quality_score_nonempty_project_above_zero(self, tmp_project: Path) -> None:
        structure, analyses, config = _full_pipeline(tmp_project)
        composer = DocumentComposer(config)
        content = composer.compose(structure, analyses)
        score = composer.estimate_quality_score(content)
        assert score > 0


class TestFullPipeline:
    def test_pipeline_on_python_project(self, tmp_project: Path) -> None:
        structure, analyses, config = _full_pipeline(tmp_project)
        composer = DocumentComposer(config)
        result = composer.compose(structure, analyses)
        assert "Python" in result
        assert "## Tech Stack" in result

    def test_pipeline_on_react_project(self, tmp_react_project: Path) -> None:
        structure, analyses, config = _full_pipeline(tmp_react_project)
        composer = DocumentComposer(config)
        result = composer.compose(structure, analyses, project_name="my-react-app")
        assert "# CLAUDE.md — my-react-app" in result
        assert "TypeScript" in result

    def test_pipeline_self_dogfood(self) -> None:
        """Run the full pipeline on claudemd-forge itself."""
        root = Path(__file__).parent.parent
        structure, analyses, config = _full_pipeline(root)
        composer = DocumentComposer(config)
        result = composer.compose(structure, analyses, project_name="claudemd-forge")
        assert "# CLAUDE.md — claudemd-forge" in result
        assert "Python" in result
        score = composer.estimate_quality_score(result)
        assert score > 40
