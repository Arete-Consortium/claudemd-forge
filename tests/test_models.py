"""Tests for Pydantic data models."""

from __future__ import annotations

from pathlib import Path

import pydantic
import pytest

from claudemd_forge.models import (
    AnalysisResult,
    AuditFinding,
    AuditReport,
    FileInfo,
    ForgeConfig,
    FrameworkPreset,
    PresetPack,
    ProjectStructure,
)


class TestFileInfo:
    def test_create(self) -> None:
        fi = FileInfo(path=Path("src/main.py"), extension=".py", size_bytes=1024)
        assert fi.path == Path("src/main.py")
        assert fi.extension == ".py"
        assert fi.size_bytes == 1024
        assert fi.line_count is None

    def test_with_line_count(self) -> None:
        fi = FileInfo(path=Path("a.py"), extension=".py", size_bytes=100, line_count=42)
        assert fi.line_count == 42

    def test_round_trip(self) -> None:
        fi = FileInfo(path=Path("x.rs"), extension=".rs", size_bytes=256, line_count=10)
        dumped = fi.model_dump()
        restored = FileInfo.model_validate(dumped)
        assert restored == fi


class TestProjectStructure:
    def test_create_minimal(self) -> None:
        ps = ProjectStructure(
            root=Path("/tmp/proj"),
            files=[],
            directories=[],
            total_files=0,
            total_lines=0,
        )
        assert ps.total_files == 0
        assert ps.languages == {}
        assert ps.primary_language is None

    def test_with_languages(self) -> None:
        ps = ProjectStructure(
            root=Path("/tmp/proj"),
            files=[],
            directories=[],
            total_files=5,
            total_lines=200,
            primary_language="Python",
            languages={"Python": 3, "TypeScript": 2},
        )
        assert ps.languages["Python"] == 3

    def test_round_trip(self) -> None:
        ps = ProjectStructure(
            root=Path("/tmp/proj"),
            files=[FileInfo(path=Path("a.py"), extension=".py", size_bytes=100)],
            directories=[Path("src")],
            total_files=1,
            total_lines=10,
            languages={"Python": 1},
        )
        restored = ProjectStructure.model_validate(ps.model_dump())
        assert restored == ps


class TestAnalysisResult:
    def test_create(self) -> None:
        ar = AnalysisResult(
            category="language",
            findings={"frameworks": ["FastAPI"]},
            confidence=0.95,
            section_content="## Tech Stack\n- Python\n",
        )
        assert ar.category == "language"
        assert ar.confidence == 0.95

    def test_confidence_bounds(self) -> None:
        with pytest.raises(pydantic.ValidationError):
            AnalysisResult(
                category="test",
                findings={},
                confidence=1.5,
                section_content="",
            )

        with pytest.raises(pydantic.ValidationError):
            AnalysisResult(
                category="test",
                findings={},
                confidence=-0.1,
                section_content="",
            )

    def test_requires_all_fields(self) -> None:
        with pytest.raises(pydantic.ValidationError):
            AnalysisResult(category="test")  # type: ignore[call-arg]

    def test_round_trip(self) -> None:
        ar = AnalysisResult(
            category="patterns",
            findings={"quote_style": "double"},
            confidence=0.8,
            section_content="## Coding Standards\n",
        )
        restored = AnalysisResult.model_validate(ar.model_dump())
        assert restored == ar


class TestAuditFinding:
    def test_create(self) -> None:
        af = AuditFinding(
            severity="error",
            category="coverage",
            message="Missing common commands section",
        )
        assert af.severity == "error"
        assert af.suggestion is None

    def test_with_suggestion(self) -> None:
        af = AuditFinding(
            severity="warning",
            category="accuracy",
            message="Listed framework not found",
            suggestion="Remove or update the framework reference",
        )
        assert af.suggestion is not None

    def test_invalid_severity(self) -> None:
        with pytest.raises(pydantic.ValidationError):
            AuditFinding(severity="critical", category="test", message="bad")  # type: ignore[arg-type]


class TestAuditReport:
    def test_create(self) -> None:
        report = AuditReport(
            score=75,
            findings=[],
            missing_sections=["domain_context"],
            recommendations=["Add domain context section"],
        )
        assert report.score == 75

    def test_score_bounds(self) -> None:
        with pytest.raises(pydantic.ValidationError):
            AuditReport(score=101, findings=[], missing_sections=[], recommendations=[])
        with pytest.raises(pydantic.ValidationError):
            AuditReport(score=-1, findings=[], missing_sections=[], recommendations=[])


class TestForgeConfig:
    def test_defaults(self) -> None:
        config = ForgeConfig(root_path=Path("/tmp"))
        assert config.preset == "default"
        assert config.max_file_size_kb == 500
        assert config.max_files == 5000
        assert "node_modules" in config.exclude_patterns
        assert ".git" in config.exclude_patterns

    def test_exclude_patterns_includes_runtime_artifacts(self) -> None:
        config = ForgeConfig(root_path=Path("/tmp"))
        assert ".coverage" in config.exclude_patterns
        assert "htmlcov" in config.exclude_patterns
        assert "*.pyc" in config.exclude_patterns

    def test_custom_values(self) -> None:
        config = ForgeConfig(
            root_path=Path("/tmp"),
            output_path=Path("/tmp/CLAUDE.md"),
            preset="python-fastapi",
            max_file_size_kb=1000,
        )
        assert config.output_path == Path("/tmp/CLAUDE.md")
        assert config.preset == "python-fastapi"

    def test_round_trip(self) -> None:
        config = ForgeConfig(root_path=Path("/tmp/project"))
        restored = ForgeConfig.model_validate(config.model_dump())
        assert restored == config


class TestFrameworkPreset:
    def test_create(self) -> None:
        preset = FrameworkPreset(
            name="Python + FastAPI",
            description="FastAPI web application",
            coding_standards=["Use async/await"],
            anti_patterns=["Do NOT use os.path"],
            common_commands={"test": "pytest"},
        )
        assert preset.name == "Python + FastAPI"
        assert len(preset.coding_standards) == 1
        assert preset.extra_sections == {}

    def test_round_trip(self) -> None:
        preset = FrameworkPreset(
            name="Rust",
            description="Rust app",
            coding_standards=["Use Result<T, E>"],
            anti_patterns=["Do NOT use .unwrap()"],
            common_commands={"build": "cargo build"},
        )
        restored = FrameworkPreset.model_validate(preset.model_dump())
        assert restored == preset


class TestPresetPack:
    def test_defaults(self) -> None:
        pack = PresetPack(name="Default", description="Auto-detect")
        assert pack.auto_detect is False
        assert pack.sections is None
        assert pack.extra_sections == []

    def test_minimal_pack(self) -> None:
        pack = PresetPack(
            name="Minimal",
            description="Bare essentials",
            sections=["header", "commands", "anti_patterns"],
        )
        assert len(pack.sections) == 3
