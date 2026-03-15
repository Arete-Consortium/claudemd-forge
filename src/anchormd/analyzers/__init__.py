"""Codebase analyzers for AnchorMD."""

from __future__ import annotations

from anchormd.analyzers.commands import CommandAnalyzer
from anchormd.analyzers.domain import DomainAnalyzer
from anchormd.analyzers.github import GitHubAnalyzer
from anchormd.analyzers.language import LanguageAnalyzer
from anchormd.analyzers.patterns import PatternAnalyzer
from anchormd.analyzers.skills import SkillsAnalyzer
from anchormd.analyzers.tech_debt import TechDebtAnalyzer
from anchormd.models import AnalysisResult, ForgeConfig, ProjectStructure

ANALYZERS: list[type] = [
    LanguageAnalyzer,
    PatternAnalyzer,
    CommandAnalyzer,
    DomainAnalyzer,
    SkillsAnalyzer,
    TechDebtAnalyzer,
    GitHubAnalyzer,
]


def run_all(structure: ProjectStructure, config: ForgeConfig) -> list[AnalysisResult]:
    """Run all registered analyzers and return results."""
    results: list[AnalysisResult] = []
    for analyzer_cls in ANALYZERS:
        analyzer = analyzer_cls()
        result = analyzer.analyze(structure, config)
        results.append(result)
    return results
