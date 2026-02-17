"""Pydantic models for all ClaudeMD Forge data structures."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from claudemd_forge.config import DEFAULT_EXCLUDE_DIRS


class FileInfo(BaseModel):
    """Information about a single file in the project."""

    path: Path
    extension: str
    size_bytes: int
    line_count: int | None = None


class ProjectStructure(BaseModel):
    """Complete structural inventory of a scanned project."""

    root: Path
    files: list[FileInfo]
    directories: list[Path]
    total_files: int
    total_lines: int
    primary_language: str | None = None
    languages: dict[str, int] = Field(default_factory=dict)
    version: str | None = None
    description: str | None = None
    declared_dependencies: dict[str, list[str]] = Field(default_factory=dict)


class AnalysisResult(BaseModel):
    """Result from a single analyzer pass."""

    category: str
    findings: dict[str, Any]
    confidence: float = Field(ge=0.0, le=1.0)
    section_content: str


class AuditFinding(BaseModel):
    """A single finding from the CLAUDE.md auditor."""

    severity: Literal["error", "warning", "info"]
    category: str
    message: str
    suggestion: str | None = None


class AuditReport(BaseModel):
    """Complete audit report for a CLAUDE.md file."""

    score: int = Field(ge=0, le=100)
    findings: list[AuditFinding]
    missing_sections: list[str]
    recommendations: list[str]


class ForgeConfig(BaseModel):
    """Configuration for a ClaudeMD Forge run."""

    root_path: Path
    output_path: Path | None = None
    preset: str = "default"
    include_patterns: list[str] = Field(default_factory=lambda: ["*"])
    exclude_patterns: list[str] = Field(default_factory=lambda: list(DEFAULT_EXCLUDE_DIRS))
    max_file_size_kb: int = 500
    max_files: int = 5000


class FrameworkPreset(BaseModel):
    """Framework-specific CLAUDE.md template preset."""

    name: str
    description: str
    coding_standards: list[str]
    anti_patterns: list[str]
    common_commands: dict[str, str]
    extra_sections: dict[str, str] = Field(default_factory=dict)


class PresetPack(BaseModel):
    """Curated preset combination for a project type."""

    name: str
    description: str
    auto_detect: bool = False
    sections: list[str] | None = None
    extra_sections: list[str] = Field(default_factory=list)
