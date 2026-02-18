"""Section generators for CLAUDE.md."""

from __future__ import annotations

import fnmatch

from claudemd_forge.config import ARCHITECTURE_EXCLUDE_FILES
from claudemd_forge.models import AnalysisResult, ProjectStructure

# Anti-pattern rules keyed by detection signal.
_ANTI_PATTERN_RULES: dict[str, list[str]] = {
    "Python": [
        "Do NOT use `os.path` — use `pathlib.Path` everywhere",
        "Do NOT use bare `except:` — catch specific exceptions",
        "Do NOT use mutable default arguments",
        "Do NOT use `print()` for logging — use the `logging` module",
    ],
    "react": [
        "Do NOT use class components — use functional components with hooks",
        "Do NOT mutate state directly — use immutable patterns",
        "Do NOT use `useEffect` for derived state — use `useMemo`",
    ],
    "TypeScript": [
        "Do NOT use `any` type — define proper type interfaces",
        "Do NOT use `var` — use `const` or `let`",
    ],
    "fastapi": [
        "Do NOT use synchronous database calls in async endpoints",
        "Do NOT return raw dicts — use Pydantic response models",
    ],
    "Rust": [
        "Do NOT use `.unwrap()` in production code — use proper error handling",
        "Do NOT use `unsafe` without a safety comment",
        "Do NOT clone when a reference will do",
    ],
    "django": [
        "Do NOT use raw SQL when the ORM can handle it",
        "Do NOT put business logic in views — use service layers",
    ],
    "Docker": [
        "Do NOT hardcode secrets in Dockerfiles — use environment variables",
        "Do NOT use `latest` tag — pin specific versions",
    ],
    "_always": [
        "Do NOT commit secrets, API keys, or credentials",
        "Do NOT skip writing tests for new code",
    ],
}


class SectionGenerator:
    """Generates individual CLAUDE.md sections from analysis results."""

    def generate_header(self, project_name: str, description: str = "") -> str:
        """Generate the CLAUDE.md header."""
        lines = [f"# CLAUDE.md — {project_name}", ""]
        if description:
            lines.append(description)
            lines.append("")
        return "\n".join(lines)

    def generate_project_overview(
        self, project_name: str, description: str = "", structure_description: str = ""
    ) -> str:
        """Generate the project overview section."""
        lines = ["## Project Overview", ""]
        desc = description or structure_description
        if desc:
            lines.append(desc)
        else:
            lines.append(f"{project_name} — TODO: Add project description.")
        lines.append("")
        return "\n".join(lines)

    def generate_current_state(self, structure: ProjectStructure) -> str:
        """Generate the current state section."""
        lang_count = len(structure.languages)
        lines = ["## Current State", ""]
        if structure.version:
            lines.append(f"- **Version**: {structure.version}")
        lines.extend(
            [
                f"- **Language**: {structure.primary_language or 'Unknown'}",
                f"- **Files**: {structure.total_files} across {lang_count} languages",
                f"- **Lines**: {structure.total_lines:,}",
                "",
            ]
        )
        return "\n".join(lines)

    def generate_architecture(self, structure: ProjectStructure) -> str:
        """Generate the architecture section with a directory tree."""
        lines = ["## Architecture", "", "```"]

        # Build a 2-level deep tree.
        root_name = structure.root.name
        lines.append(f"{root_name}/")

        # Get top-level dirs and files.
        top_dirs: set[str] = set()
        top_files: set[str] = set()
        second_level: dict[str, list[str]] = {}

        for d in structure.directories:
            parts = d.parts
            if len(parts) == 1:
                top_dirs.add(parts[0])
            elif len(parts) == 2:
                parent = parts[0]
                if parent not in second_level:
                    second_level[parent] = []
                second_level[parent].append(parts[1])

        for f in structure.files:
            parts = f.path.parts
            if len(parts) == 1:
                top_files.add(parts[0])

        for d in sorted(top_dirs):
            lines.append(f"├── {d}/")
            if d in second_level:
                children = sorted(second_level[d])
                for i, child in enumerate(children[:10]):
                    prefix = "│   └──" if i == len(children) - 1 else "│   ├──"
                    lines.append(f"{prefix} {child}/")
                if len(children) > 10:
                    lines.append(f"│   └── ... ({len(children) - 10} more)")

        # Filter runtime artifacts from top-level files.
        filtered_files = {
            f
            for f in top_files
            if not any(fnmatch.fnmatch(f, pat) for pat in ARCHITECTURE_EXCLUDE_FILES)
        }

        for f_name in sorted(filtered_files):
            lines.append(f"├── {f_name}")

        lines.append("```")
        lines.append("")
        return "\n".join(lines)

    def generate_tech_stack(self, analysis: AnalysisResult) -> str:
        """Use language analyzer's section_content."""
        return analysis.section_content

    def generate_coding_standards(self, analysis: AnalysisResult) -> str:
        """Use pattern analyzer's section_content."""
        return analysis.section_content

    def generate_commands(self, analysis: AnalysisResult) -> str:
        """Use command analyzer's section_content."""
        return analysis.section_content

    def generate_domain_context(self, analysis: AnalysisResult) -> str:
        """Use domain analyzer's section_content."""
        return analysis.section_content

    def generate_anti_patterns(
        self, structure: ProjectStructure, analyses: list[AnalysisResult]
    ) -> str:
        """Generate anti-patterns section based on detected stack."""
        patterns: list[str] = list(_ANTI_PATTERN_RULES["_always"])

        # Detect what's in the project.
        signals: set[str] = set()
        if structure.primary_language:
            signals.add(structure.primary_language)

        for analysis in analyses:
            if analysis.category == "language":
                frameworks = analysis.findings.get("frameworks", [])
                if isinstance(frameworks, list):
                    signals.update(frameworks)
                runtime = analysis.findings.get("runtime", [])
                if isinstance(runtime, list):
                    signals.update(runtime)
                langs = analysis.findings.get("languages", {})
                if isinstance(langs, dict):
                    signals.update(langs.keys())

        for signal in signals:
            if signal in _ANTI_PATTERN_RULES:
                patterns.extend(_ANTI_PATTERN_RULES[signal])

        if not patterns:
            return ""

        # Deduplicate while preserving order.
        seen: set[str] = set()
        unique: list[str] = []
        for p in patterns:
            if p not in seen:
                seen.add(p)
                unique.append(p)

        lines = ["## Anti-Patterns (Do NOT Do)", ""]
        for p in unique:
            lines.append(f"- {p}")
        lines.append("")
        return "\n".join(lines)

    def generate_dependencies(
        self, analyses: list[AnalysisResult], structure: ProjectStructure | None = None
    ) -> str:
        """Generate dependencies section from declared deps or analyzer findings."""
        lines = ["## Dependencies", ""]

        # Prefer declared dependencies from manifest files.
        if structure and structure.declared_dependencies:
            core = structure.declared_dependencies.get("core", [])
            if core:
                lines.append("### Core")
                for dep in core[:15]:
                    lines.append(f"- {dep}")
                lines.append("")
            dev = structure.declared_dependencies.get("dev", [])
            if dev:
                lines.append("### Dev")
                for dep in dev[:10]:
                    lines.append(f"- {dep}")
                lines.append("")
        else:
            # Fallback to framework-detection behavior.
            for analysis in analyses:
                if analysis.category != "language":
                    continue

                frameworks = analysis.findings.get("frameworks", [])
                if frameworks:
                    lines.append("### Core")
                    for fw in frameworks:
                        lines.append(f"- {fw}")
                    lines.append("")

                toolchains = analysis.findings.get("toolchains", {})
                if isinstance(toolchains, dict):
                    test_fws = toolchains.get("test_frameworks", [])
                    linters = toolchains.get("linters", [])
                    if test_fws or linters:
                        lines.append("### Dev")
                        for tool in test_fws + linters:
                            lines.append(f"- {tool}")
                        lines.append("")

        if len(lines) <= 2:
            return ""
        return "\n".join(lines)

    def generate_git_conventions(self, structure: ProjectStructure) -> str:
        """Generate git conventions section."""
        lines = [
            "## Git Conventions",
            "",
            "- Commit messages: Conventional commits"
            " (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)",
            "- Branch naming: `feat/description`, `fix/description`",
            "- Run tests before committing",
            "",
        ]
        return "\n".join(lines)
