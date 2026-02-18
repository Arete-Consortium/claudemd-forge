"""Document composer that assembles sections into a complete CLAUDE.md."""

from __future__ import annotations

import re

from claudemd_forge.config import SECTION_ORDER
from claudemd_forge.models import AnalysisResult, ForgeConfig, ProjectStructure

from .sections import SectionGenerator


class DocumentComposer:
    """Assembles sections into a complete CLAUDE.md document."""

    def __init__(self, config: ForgeConfig) -> None:
        self.config = config
        self._gen = SectionGenerator()

    def compose(
        self,
        structure: ProjectStructure,
        analyses: list[AnalysisResult],
        project_name: str | None = None,
    ) -> str:
        """Compose all sections into final CLAUDE.md content."""
        name = project_name or structure.root.name

        # Build a lookup by category.
        by_category: dict[str, AnalysisResult] = {}
        for a in analyses:
            by_category[a.category] = a

        # Generate each section.
        section_map: dict[str, str] = {}

        section_map["header"] = self._gen.generate_header(name)
        section_map["project_overview"] = self._gen.generate_project_overview(
            name, structure_description=structure.description or ""
        )
        section_map["current_state"] = self._gen.generate_current_state(structure)
        section_map["architecture"] = self._gen.generate_architecture(structure)

        if "language" in by_category:
            section_map["tech_stack"] = self._gen.generate_tech_stack(by_category["language"])
        if "patterns" in by_category:
            section_map["coding_standards"] = self._gen.generate_coding_standards(
                by_category["patterns"]
            )
        if "commands" in by_category:
            section_map["common_commands"] = self._gen.generate_commands(by_category["commands"])
        if "domain" in by_category:
            section_map["domain_context"] = self._gen.generate_domain_context(by_category["domain"])

        section_map["anti_patterns"] = self._gen.generate_anti_patterns(structure, analyses)
        section_map["dependencies"] = self._gen.generate_dependencies(analyses, structure)
        section_map["git_conventions"] = self._gen.generate_git_conventions(structure)

        # Assemble in order.
        parts: list[str] = []
        for section_name in SECTION_ORDER:
            content = section_map.get(section_name, "")
            if content and content.strip():
                parts.append(content)

        result = "\n".join(parts)
        return self._clean_output(result)

    def _clean_output(self, content: str) -> str:
        """Remove excessive blank lines, normalize heading levels, ensure trailing newline."""
        # Collapse 3+ consecutive blank lines to 2.
        content = re.sub(r"\n{3,}", "\n\n", content)
        # Ensure single trailing newline.
        content = content.rstrip() + "\n"
        return content

    def estimate_quality_score(self, content: str) -> int:
        """Score 0-100 based on section coverage and content depth."""
        score = 0

        # Section coverage (max 60 points).
        expected_headings = [
            "Project Overview",
            "Current State",
            "Architecture",
            "Tech Stack",
            "Coding Standards",
            "Common Commands",
            "Anti-Patterns",
            "Dependencies",
            "Git Conventions",
        ]
        present = sum(1 for h in expected_headings if f"## {h}" in content)
        score += int((present / len(expected_headings)) * 60)

        # Content depth (max 20 points).
        lines = content.splitlines()
        if len(lines) > 50:
            score += 10
        if len(lines) > 100:
            score += 5
        if len(lines) > 150:
            score += 5

        # Code blocks present (max 10 points).
        code_blocks = content.count("```")
        if code_blocks >= 2:
            score += 10
        elif code_blocks >= 1:
            score += 5

        # Specificity — bullet points with bold labels (max 10 points).
        bold_bullets = len(re.findall(r"- \*\*\w+", content))
        if bold_bullets > 5:
            score += 10
        elif bold_bullets > 2:
            score += 5

        return min(100, score)
