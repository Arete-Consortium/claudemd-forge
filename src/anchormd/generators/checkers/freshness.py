"""Freshness checker for CLAUDE.md audits."""

from __future__ import annotations

import re

from anchormd.models import AuditFinding, ProjectStructure


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
            if "/" not in ref:
                continue
            # Skip absolute/system paths — these are intentional references
            # to OS resources (e.g. /dev/input/by-id/), not project files.
            if ref.startswith("/"):
                continue
            last = ref.rstrip("/").split("/")[-1]
            if "." not in last and not ref.endswith("/"):
                continue

            normalized = ref.rstrip("/")
            if normalized in all_existing:
                continue
            # Prefix match: if ref looks like a directory, accept when any
            # scanned path lives under it. Covers refs whose exact dir
            # wasn't added (e.g. scanner skipped it) but children exist.
            prefix = normalized + "/"
            if any(p.startswith(prefix) for p in all_existing):
                continue

            findings.append(
                AuditFinding(
                    severity="warning",
                    category="freshness",
                    message=(f"References path `{ref}` which doesn't exist in the project"),
                    suggestion="Update or remove stale file references",
                )
            )

        return findings
