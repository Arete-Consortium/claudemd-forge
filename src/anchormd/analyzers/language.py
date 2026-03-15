"""Language, framework, and toolchain analyzer."""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path

from anchormd.config import FRAMEWORK_INDICATORS
from anchormd.models import AnalysisResult, ForgeConfig, ProjectStructure

logger = logging.getLogger(__name__)


class LanguageAnalyzer:
    """Detects languages, frameworks, toolchains, and package managers."""

    def analyze(self, structure: ProjectStructure, config: ForgeConfig) -> AnalysisResult:
        """Detect everything about the project's tech stack."""
        findings: dict[str, object] = {}
        root = structure.root

        findings["languages"] = structure.languages
        findings["primary_language"] = structure.primary_language
        findings["frameworks"] = self._detect_frameworks(root)
        findings["package_managers"] = self._detect_package_managers(root)
        findings["toolchains"] = self._detect_toolchains(root)
        findings["runtime"] = self._detect_runtime(root)
        findings["ci_cd"] = self._detect_ci_cd(root)

        # Calculate confidence based on how many signals we found.
        signals = sum(
            1
            for v in findings.values()
            if v and (isinstance(v, (list, dict)) and len(v) > 0 or isinstance(v, str))
        )
        confidence = min(1.0, signals / 7.0)

        section = self._render_section(findings)
        return AnalysisResult(
            category="language",
            findings=findings,
            confidence=confidence,
            section_content=section,
        )

    def _detect_frameworks(self, root: Path) -> list[str]:
        """Detect frameworks by checking indicator files and dependency contents."""
        detected: list[str] = []
        for framework, indicators in FRAMEWORK_INDICATORS.items():
            for indicator in indicators:
                if ":" in indicator:
                    filepath, search_str = indicator.split(":", 1)
                    target = root / filepath
                    if target.is_file():
                        try:
                            content = target.read_text(errors="replace")
                            if search_str.lower() in content.lower():
                                detected.append(framework)
                                break
                        except OSError:
                            continue
                else:
                    if (root / indicator).exists():
                        detected.append(framework)
                        break
        return sorted(set(detected))

    def _detect_package_managers(self, root: Path) -> list[str]:
        """Detect package managers from lockfiles and config files."""
        managers: list[str] = []
        checks = {
            "npm": ["package-lock.json"],
            "yarn": ["yarn.lock"],
            "pnpm": ["pnpm-lock.yaml"],
            "bun": ["bun.lockb"],
            "pip": ["requirements.txt"],
            "uv": ["uv.lock"],
            "poetry": ["poetry.lock"],
            "cargo": ["Cargo.lock"],
            "go modules": ["go.sum"],
        }
        for manager, files in checks.items():
            for f in files:
                if (root / f).is_file():
                    managers.append(manager)
                    break
        # Also check pyproject.toml for build backend hints.
        pyproject = root / "pyproject.toml"
        if pyproject.is_file() and "pip" not in managers and "poetry" not in managers:
            try:
                content = pyproject.read_text(errors="replace")
                if "setuptools" in content or "hatchling" in content or "flit" in content:
                    managers.append("pip")
            except OSError:
                pass  # Best-effort read; skip if unreadable
        return sorted(set(managers))

    def _detect_toolchains(self, root: Path) -> dict[str, list[str]]:
        """Detect linters, formatters, and type checkers."""
        linters: list[str] = []
        formatters: list[str] = []
        type_checkers: list[str] = []

        # Check config files for tool presence.
        tool_map = {
            "linters": {
                "ruff": [".ruff.toml", "ruff.toml"],
                "eslint": [".eslintrc", ".eslintrc.js", ".eslintrc.json", ".eslintrc.yml"],
                "flake8": [".flake8"],
                "pylint": [".pylintrc", "pylintrc"],
                "clippy": [],  # detected via Cargo.toml
            },
            "formatters": {
                "prettier": [".prettierrc", ".prettierrc.js", ".prettierrc.json"],
                "black": [],
                "ruff": [],  # ruff can also format
            },
            "type_checkers": {
                "mypy": ["mypy.ini", ".mypy.ini"],
                "pyright": ["pyrightconfig.json"],
            },
        }

        # Check pyproject.toml for tool configs.
        pyproject = root / "pyproject.toml"
        pyproject_content = ""
        if pyproject.is_file():
            with contextlib.suppress(OSError):
                pyproject_content = pyproject.read_text(errors="replace")

        # Check package.json for devDependencies.
        pkg_json_content = ""
        pkg_json = root / "package.json"
        if pkg_json.is_file():
            with contextlib.suppress(OSError):
                pkg_json_content = pkg_json.read_text(errors="replace")

        combined = pyproject_content + pkg_json_content

        for tool, configs in tool_map["linters"].items():
            if (
                any((root / c).is_file() for c in configs)
                or f"[tool.{tool}" in pyproject_content
                or f'"{tool}"' in pkg_json_content
            ):
                linters.append(tool)

        for tool, configs in tool_map["formatters"].items():
            if (
                any((root / c).is_file() for c in configs)
                or f"[tool.{tool}" in pyproject_content
                or f'"{tool}"' in combined
            ):
                formatters.append(tool)

        for tool, configs in tool_map["type_checkers"].items():
            if any((root / c).is_file() for c in configs) or f"[tool.{tool}" in pyproject_content:
                type_checkers.append(tool)

        # TypeScript implies tsc type checking.
        if (root / "tsconfig.json").is_file():
            type_checkers.append("tsc")

        # Rust implies clippy.
        if (root / "Cargo.toml").is_file():
            linters.append("clippy")

        # Detect test frameworks.
        test_frameworks: list[str] = []
        if "pytest" in combined:
            test_frameworks.append("pytest")
        if "vitest" in combined:
            test_frameworks.append("vitest")
        if "jest" in combined:
            test_frameworks.append("jest")
        if "mocha" in combined:
            test_frameworks.append("mocha")
        if (root / "Cargo.toml").is_file():
            test_frameworks.append("cargo test")

        return {
            "linters": sorted(set(linters)),
            "formatters": sorted(set(formatters)),
            "type_checkers": sorted(set(type_checkers)),
            "test_frameworks": sorted(set(test_frameworks)),
        }

    def _detect_runtime(self, root: Path) -> list[str]:
        """Detect Docker, Makefiles, etc."""
        runtime: list[str] = []
        checks = {
            "Docker": ["Dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml"],
            "Makefile": ["Makefile", "makefile"],
            "justfile": ["justfile", "Justfile"],
        }
        for name, files in checks.items():
            if any((root / f).is_file() for f in files):
                runtime.append(name)
        return runtime

    def _detect_ci_cd(self, root: Path) -> list[str]:
        """Detect CI/CD systems."""
        ci: list[str] = []
        if (root / ".github" / "workflows").is_dir():
            ci.append("GitHub Actions")
        if (root / ".gitlab-ci.yml").is_file():
            ci.append("GitLab CI")
        if (root / "Jenkinsfile").is_file():
            ci.append("Jenkins")
        if (root / ".circleci").is_dir():
            ci.append("CircleCI")
        if (root / ".travis.yml").is_file():
            ci.append("Travis CI")
        return ci

    def _render_section(self, findings: dict[str, object]) -> str:
        """Render the tech stack section as markdown."""
        lines: list[str] = ["## Tech Stack", ""]

        primary = findings.get("primary_language")
        langs = findings.get("languages", {})
        if primary:
            other_langs = [k for k in langs if k != primary]  # type: ignore[union-attr]
            lang_str = str(primary)
            if other_langs:
                lang_str += f", {', '.join(other_langs)}"
            lines.append(f"- **Language**: {lang_str}")

        frameworks = findings.get("frameworks", [])
        if frameworks:
            lines.append(f"- **Framework**: {', '.join(frameworks)}")  # type: ignore[arg-type]

        pkg_mgrs = findings.get("package_managers", [])
        if pkg_mgrs:
            lines.append(f"- **Package Manager**: {', '.join(pkg_mgrs)}")  # type: ignore[arg-type]

        toolchains = findings.get("toolchains", {})
        if isinstance(toolchains, dict):
            for category, tools in toolchains.items():
                if tools:
                    label = category.replace("_", " ").title()
                    lines.append(f"- **{label}**: {', '.join(tools)}")

        runtime = findings.get("runtime", [])
        if runtime:
            lines.append(f"- **Runtime**: {', '.join(runtime)}")  # type: ignore[arg-type]

        ci = findings.get("ci_cd", [])
        if ci:
            lines.append(f"- **CI/CD**: {', '.join(ci)}")  # type: ignore[arg-type]

        lines.append("")
        return "\n".join(lines)
