"""Anti-pattern checker for CLAUDE.md audits."""

from __future__ import annotations

import re

from claudemd_forge.models import AuditFinding


class AntiPatternChecker:
    """Check for common CLAUDE.md anti-patterns."""

    def check(self, content: str) -> list[AuditFinding]:
        """Return findings for detected anti-patterns."""
        findings: list[AuditFinding] = []
        lines = content.splitlines()
        line_count = len(lines)

        if line_count > 500:
            findings.append(
                AuditFinding(
                    severity="warning",
                    category="anti_pattern",
                    message=(f"CLAUDE.md is {line_count} lines — too long, agents lose context"),
                    suggestion="Trim to under 300 lines, focus on essentials",
                )
            )

        if line_count < 20:
            findings.append(
                AuditFinding(
                    severity="warning",
                    category="anti_pattern",
                    message=(
                        f"CLAUDE.md is only {line_count} lines — too short for useful context"
                    ),
                    suggestion=("Add more sections: overview, commands, coding standards"),
                )
            )

        for line in lines:
            if re.search(r"\bTODO\b|\bFIXME\b", line):
                findings.append(
                    AuditFinding(
                        severity="warning",
                        category="anti_pattern",
                        message=("Contains TODO/FIXME items (stale planning artifacts)"),
                        suggestion="Resolve or remove TODO items from CLAUDE.md",
                    )
                )
                break

        conversation_markers = [
            "can you",
            "please help",
            "i want you to",
            "let me know",
            "sure, I",
            "here's what",
            "I'll help",
        ]
        lower_content = content.lower()
        for marker in conversation_markers:
            if marker in lower_content:
                findings.append(
                    AuditFinding(
                        severity="warning",
                        category="anti_pattern",
                        message=("Contains conversation fragments (copy-paste from AI chat)"),
                        suggestion=("Use declarative style, not conversational prompts"),
                    )
                )
                break

        first_person = re.findall(r"\b(I want|We use|I need|Our team|We have)\b", content)
        if first_person:
            findings.append(
                AuditFinding(
                    severity="info",
                    category="anti_pattern",
                    message=("Uses first-person language instead of declarative style"),
                    suggestion=('Use declarative: "Use pytest" instead of "We use pytest"'),
                )
            )

        if content.count("```") % 2 != 0:
            findings.append(
                AuditFinding(
                    severity="info",
                    category="anti_pattern",
                    message=("Contains unclosed code block (odd number of ``` markers)"),
                    suggestion="Close all code blocks with matching ```",
                )
            )

        return findings
