"""Codebase analyzers for ClaudeMD Forge."""

from __future__ import annotations

from claudemd_forge.analyzers.commands import CommandAnalyzer
from claudemd_forge.analyzers.domain import DomainAnalyzer
from claudemd_forge.analyzers.language import LanguageAnalyzer
from claudemd_forge.analyzers.patterns import PatternAnalyzer
from claudemd_forge.analyzers.skills import SkillsAnalyzer
from claudemd_forge.models import AnalysisResult, ForgeConfig, ProjectStructure

ANALYZERS: list[type] = [
    LanguageAnalyzer,
    PatternAnalyzer,
    CommandAnalyzer,
    DomainAnalyzer,
    SkillsAnalyzer,
]


def run_all(structure: ProjectStructure, config: ForgeConfig) -> list[AnalysisResult]:
    """Run all registered analyzers and return results."""
    results: list[AnalysisResult] = []
    for analyzer_cls in ANALYZERS:
        analyzer = analyzer_cls()
        result = analyzer.analyze(structure, config)
        results.append(result)
    return results
