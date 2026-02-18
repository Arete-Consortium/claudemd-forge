"""Specificity checker for CLAUDE.md audits."""

from __future__ import annotations

from claudemd_forge.models import AuditFinding

_VAGUE_PHRASES = [
    "follow best practices",
    "use standard conventions",
    "write clean code",
    "keep it simple",
    "be consistent",
    "use appropriate",
    "handle errors properly",
]


class SpecificityChecker:
    """Check for vague or generic content that should be specific."""

    def check(self, content: str) -> list[AuditFinding]:
        """Return findings for vague content."""
        findings: list[AuditFinding] = []
        lower_content = content.lower()

        for phrase in _VAGUE_PHRASES:
            if phrase in lower_content:
                findings.append(
                    AuditFinding(
                        severity="warning",
                        category="specificity",
                        message=f'Contains vague phrase: "{phrase}"',
                        suggestion=("Replace with specific, actionable instructions"),
                    )
                )

        if "## Anti-Patterns" in content or "## Anti-patterns" in content:
            anti_start = content.lower().find("## anti-pattern")
            if anti_start >= 0:
                next_section = content.find("\n## ", anti_start + 1)
                anti_section = (
                    content[anti_start:next_section] if next_section > 0 else content[anti_start:]
                )
                if "```" not in anti_section and "`" not in anti_section:
                    findings.append(
                        AuditFinding(
                            severity="info",
                            category="specificity",
                            message=("Anti-patterns section lacks code examples"),
                            suggestion=("Add inline code or code blocks showing what NOT to do"),
                        )
                    )

        if "## Common Commands" in content or "## Commands" in content:
            cmd_start = content.lower().find("## common command")
            if cmd_start < 0:
                cmd_start = content.lower().find("## command")
            if cmd_start >= 0:
                next_section = content.find("\n## ", cmd_start + 1)
                cmd_section = (
                    content[cmd_start:next_section] if next_section > 0 else content[cmd_start:]
                )
                if "```" not in cmd_section:
                    findings.append(
                        AuditFinding(
                            severity="info",
                            category="specificity",
                            message=("Commands section lacks actual command strings"),
                            suggestion=("Add code blocks with runnable commands"),
                        )
                    )

        return findings
