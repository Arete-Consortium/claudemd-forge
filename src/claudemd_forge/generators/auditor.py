"""CLAUDE.md auditor — evaluates existing files against best practices."""

from __future__ import annotations

from claudemd_forge.generators.checkers import (
    AccuracyChecker,
    AntiPatternChecker,
    CoverageChecker,
    FreshnessChecker,
    SpecificityChecker,
)
from claudemd_forge.generators.checkers.coverage import REQUIRED_SECTIONS
from claudemd_forge.models import (
    AnalysisResult,
    AuditFinding,
    AuditReport,
    ForgeConfig,
    ProjectStructure,
)


class ClaudeMdAuditor:
    """Audits an existing CLAUDE.md against the actual codebase and best practices."""

    def __init__(self, config: ForgeConfig) -> None:
        self.config = config
        self._coverage = CoverageChecker()
        self._accuracy = AccuracyChecker()
        self._anti_patterns = AntiPatternChecker()
        self._specificity = SpecificityChecker()
        self._freshness = FreshnessChecker()

    def audit(
        self,
        claude_md_content: str,
        structure: ProjectStructure,
        analyses: list[AnalysisResult],
    ) -> AuditReport:
        """Full audit producing scored report with findings."""
        findings: list[AuditFinding] = []

        findings.extend(self._coverage.check(claude_md_content))
        findings.extend(self._accuracy.check(claude_md_content, structure, analyses))
        findings.extend(self._anti_patterns.check(claude_md_content))
        findings.extend(self._specificity.check(claude_md_content))
        findings.extend(self._freshness.check(claude_md_content, structure))

        section_count = sum(1 for name in REQUIRED_SECTIONS if f"## {name}" in claude_md_content)
        missing = [name for name in REQUIRED_SECTIONS if f"## {name}" not in claude_md_content]

        score = self._calculate_score(findings, section_count)
        recommendations = self._generate_recommendations(findings, missing)

        return AuditReport(
            score=score,
            findings=findings,
            missing_sections=missing,
            recommendations=recommendations,
        )

    def _calculate_score(self, findings: list[AuditFinding], section_count: int) -> int:
        """Score 0-100 based on findings severity and coverage."""
        base_score = 100

        for f in findings:
            if f.severity == "error":
                base_score -= 15
            elif f.severity == "warning":
                base_score -= 5
            elif f.severity == "info":
                base_score -= 1

        total_recommended = len(REQUIRED_SECTIONS)
        section_bonus = int((section_count / total_recommended) * 20)

        final = base_score + section_bonus
        return max(0, min(100, final))

    def _generate_recommendations(
        self, findings: list[AuditFinding], missing_sections: list[str]
    ) -> list[str]:
        """Generate actionable recommendations."""
        recs: list[str] = []

        critical_missing = [s for s in missing_sections if REQUIRED_SECTIONS.get(s) == "error"]
        if critical_missing:
            recs.append(f"Add missing critical sections: {', '.join(critical_missing)}")

        accuracy_errors = [
            f for f in findings if f.category == "accuracy" and f.severity == "error"
        ]
        if accuracy_errors:
            recs.append("Fix accuracy issues — CLAUDE.md doesn't match actual codebase")

        anti_warnings = [f for f in findings if f.category == "anti_pattern"]
        if anti_warnings:
            recs.append("Clean up CLAUDE.md anti-patterns (TODOs, conversation fragments, etc.)")

        vague = [f for f in findings if f.category == "specificity"]
        if vague:
            recs.append("Replace vague instructions with specific, actionable guidance")

        if not recs:
            recs.append("CLAUDE.md is in good shape!")

        return recs
