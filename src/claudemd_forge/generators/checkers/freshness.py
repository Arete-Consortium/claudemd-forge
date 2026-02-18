"""Freshness checker for CLAUDE.md audits."""

from __future__ import annotations

import re

from claudemd_forge.models import AuditFinding, ProjectStructure


class FreshnessChecker:
    """Detect stale information in CLAUDE.md."""

    def check(self, content: str, structure: ProjectStructure) -> list[AuditFinding]:
        """Return findings for stale references."""
        findings: list[AuditFinding] = []

        existing_paths = {str(f.path) for f in structure.files}
        existing_dirs = {str(d) for d in structure.directories}
        all_existing = existing_paths | existing_dirs

        path_refs = re.findall(r"`([a-zA-Z_./][a-zA-Z0-9_./\-]+)`", content)
        for ref in path_refs:
            if " " in ref or ref.startswith(("pip", "npm", "cargo", "make", "git")):
                continue
            if (
                "/" in ref
                and ref not in all_existing
                and ("." in ref.split("/")[-1] or ref.endswith("/"))
            ):
                findings.append(
                    AuditFinding(
                        severity="warning",
                        category="freshness",
                        message=(f"References path `{ref}` which doesn't exist in the project"),
                        suggestion="Update or remove stale file references",
                    )
                )

        return findings
