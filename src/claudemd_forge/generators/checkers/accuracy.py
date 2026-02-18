"""Accuracy checker for CLAUDE.md audits."""

from __future__ import annotations

from claudemd_forge.models import AnalysisResult, AuditFinding, ProjectStructure


class AccuracyChecker:
    """Compare CLAUDE.md claims against actual codebase state."""

    def check(
        self,
        content: str,
        structure: ProjectStructure,
        analyses: list[AnalysisResult],
    ) -> list[AuditFinding]:
        """Return findings for inaccurate claims."""
        findings: list[AuditFinding] = []
        lower_content = content.lower()

        if "greenfield" in lower_content and structure.total_files > 50:
            findings.append(
                AuditFinding(
                    severity="error",
                    category="accuracy",
                    message=(
                        f'Says "greenfield" but project has {structure.total_files} source files'
                    ),
                    suggestion="Update the project phase description",
                )
            )

        for analysis in analyses:
            if analysis.category != "language":
                continue
            detected_frameworks = set(analysis.findings.get("frameworks", []))

            common_frameworks = {
                "react",
                "vue",
                "angular",
                "django",
                "flask",
                "fastapi",
                "express",
                "nextjs",
                "svelte",
                "spring",
            }
            for fw in common_frameworks:
                if fw in lower_content and fw not in detected_frameworks:
                    findings.append(
                        AuditFinding(
                            severity="error",
                            category="accuracy",
                            message=(f'Lists "{fw}" but it was not detected in dependencies'),
                            suggestion=(f"Remove {fw} reference or add it to dependencies"),
                        )
                    )

        return findings
