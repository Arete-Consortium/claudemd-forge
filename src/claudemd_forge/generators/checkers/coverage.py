"""Section coverage checker for CLAUDE.md audits."""

from __future__ import annotations

from claudemd_forge.models import AuditFinding

REQUIRED_SECTIONS: dict[str, str] = {
    "Project Overview": "error",
    "Common Commands": "error",
    "Architecture": "error",
    "Coding Standards": "warning",
    "Anti-Patterns": "warning",
    "Dependencies": "info",
    "Git Conventions": "info",
    "Domain Context": "info",
}


class CoverageChecker:
    """Check which recommended sections are present or missing."""

    def check(self, content: str) -> list[AuditFinding]:
        """Return findings for missing sections."""
        findings: list[AuditFinding] = []
        for section_name, severity in REQUIRED_SECTIONS.items():
            if f"## {section_name}" not in content:
                lower_content = content.lower()
                lower_name = section_name.lower()
                if lower_name not in lower_content:
                    findings.append(
                        AuditFinding(
                            severity=severity,  # type: ignore[arg-type]
                            category="coverage",
                            message=f'Missing "{section_name}" section',
                            suggestion=f"Add a ## {section_name} section with relevant content",
                        )
                    )
        return findings
