"""CLI command analyzer — detects runnable commands from config files."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from anchormd.models import AnalysisResult, ForgeConfig, ProjectStructure

logger = logging.getLogger(__name__)


class CommandAnalyzer:
    """Detects common CLI commands for the project."""

    def analyze(self, structure: ProjectStructure, config: ForgeConfig) -> AnalysisResult:
        """Extract runnable commands from config files."""
        findings: dict[str, object] = {}
        root = structure.root

        findings["npm_scripts"] = self._parse_npm_scripts(root)
        findings["makefile_targets"] = self._parse_makefile(root)
        findings["justfile_recipes"] = self._parse_justfile(root)
        findings["pyproject_scripts"] = self._parse_pyproject_scripts(root)
        findings["docker_commands"] = self._parse_docker(root)

        # Calculate confidence — more sources = more confident.
        sources = sum(1 for v in findings.values() if v)
        confidence = min(1.0, sources / 3.0) if sources else 0.1

        section = self._render_section(findings)

        return AnalysisResult(
            category="commands",
            findings=findings,
            confidence=confidence,
            section_content=section,
        )

    def _parse_npm_scripts(self, root: Path) -> dict[str, str]:
        """Parse scripts block from package.json."""
        pkg = root / "package.json"
        if not pkg.is_file():
            return {}
        try:
            data = json.loads(pkg.read_text(errors="replace"))
            return data.get("scripts", {})
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Cannot parse package.json: %s", e)
            return {}

    def _parse_makefile(self, root: Path) -> dict[str, str]:
        """Parse Makefile targets and their first recipe line."""
        for name in ("Makefile", "makefile"):
            makefile = root / name
            if makefile.is_file():
                return self._extract_makefile_targets(makefile)
        return {}

    def _extract_makefile_targets(self, path: Path) -> dict[str, str]:
        """Extract target: first_command pairs from a Makefile."""
        targets: dict[str, str] = {}
        try:
            lines = path.read_text(errors="replace").splitlines()
        except OSError:
            return targets

        current_target: str | None = None
        for line in lines:
            # Target line: "name: [deps]"
            match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_-]*)\s*:", line)
            if match and not line.startswith("\t"):
                current_target = match.group(1)
            elif current_target and line.startswith("\t"):
                # First recipe line.
                targets[current_target] = line.strip()
                current_target = None
        return targets

    def _parse_justfile(self, root: Path) -> dict[str, str]:
        """Parse justfile recipes."""
        for name in ("justfile", "Justfile"):
            jf = root / name
            if jf.is_file():
                return self._extract_justfile_recipes(jf)
        return {}

    def _extract_justfile_recipes(self, path: Path) -> dict[str, str]:
        """Extract recipe names from a justfile."""
        recipes: dict[str, str] = {}
        try:
            lines = path.read_text(errors="replace").splitlines()
        except OSError:
            return recipes

        current_recipe: str | None = None
        for line in lines:
            match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_-]*)(?:\s.*)?:", line)
            if match and not line.startswith((" ", "\t")):
                current_recipe = match.group(1)
            elif current_recipe and line.startswith((" ", "\t")) and line.strip():
                recipes[current_recipe] = line.strip()
                current_recipe = None
        return recipes

    def _parse_pyproject_scripts(self, root: Path) -> dict[str, str]:
        """Parse scripts and tool config from pyproject.toml and related files."""
        commands: dict[str, str] = {}

        # Parse pyproject.toml if present.
        pyproject = root / "pyproject.toml"
        content = ""
        if pyproject.is_file():
            try:
                content = pyproject.read_text(errors="replace")
            except OSError:
                content = ""

        if content:
            # Detect test framework.
            if "pytest" in content:
                commands["test"] = "pytest tests/ -v"
            if "[tool.ruff" in content:
                commands["lint"] = "ruff check src/ tests/"
                commands["format"] = "ruff format src/ tests/"
            if "[tool.mypy" in content:
                commands["type check"] = "mypy src/"
            if "[tool.black" in content:
                commands["format"] = "black src/ tests/"
            if "[tool.coverage" in content:
                commands["coverage"] = "pytest --cov=src/ tests/"
            if "[tool.isort" in content:
                commands["isort"] = "isort src/ tests/"

            # Parse [project.scripts] and [tool.poetry.scripts].
            for header in ("[project.scripts]", "[tool.poetry.scripts]"):
                in_scripts = False
                for line in content.splitlines():
                    if line.strip() == header:
                        in_scripts = True
                        continue
                    if in_scripts:
                        if line.startswith("["):
                            break
                        match = re.match(r'(\S+)\s*=\s*"(.+)"', line.strip())
                        if match:
                            commands[match.group(1)] = match.group(2)

            # Detect tox in pyproject.
            if "[tool.tox" in content:
                commands["tox"] = "tox"

        # Detect tox.ini file.
        tox_ini = root / "tox.ini"
        if "tox" not in commands and tox_ini.is_file():
            commands["tox"] = "tox"

        # Detect setup.cfg [tool:pytest] as fallback test command.
        if "test" not in commands:
            setup_cfg = root / "setup.cfg"
            if setup_cfg.is_file():
                try:
                    cfg = setup_cfg.read_text(errors="replace")
                    if "[tool:pytest]" in cfg:
                        commands["test"] = "pytest"
                except OSError:
                    pass  # Best-effort read; skip if unreadable

        return commands

    def _parse_docker(self, root: Path) -> dict[str, str]:
        """Extract CMD/ENTRYPOINT from Dockerfile."""
        dockerfile = root / "Dockerfile"
        if not dockerfile.is_file():
            return {}

        commands: dict[str, str] = {}
        try:
            content = dockerfile.read_text(errors="replace")
        except OSError:
            return commands

        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("CMD "):
                commands["docker CMD"] = stripped[4:].strip()
            elif stripped.startswith("ENTRYPOINT "):
                commands["docker ENTRYPOINT"] = stripped[11:].strip()

        return commands

    def _render_section(self, findings: dict[str, object]) -> str:
        """Render common commands section as markdown."""
        lines: list[str] = ["## Common Commands", ""]
        lines.append("```bash")

        any_commands = False

        npm = findings.get("npm_scripts", {})
        if npm and isinstance(npm, dict):
            for name, _cmd in npm.items():
                lines.append(f"# {name}")
                lines.append(f"npm run {name}")
            any_commands = True

        pyproject = findings.get("pyproject_scripts", {})
        if pyproject and isinstance(pyproject, dict):
            if any_commands:
                lines.append("")
            for name, cmd in pyproject.items():
                lines.append(f"# {name}")
                lines.append(cmd)
            any_commands = True

        makefile = findings.get("makefile_targets", {})
        if makefile and isinstance(makefile, dict):
            if any_commands:
                lines.append("")
            for target, _cmd in makefile.items():
                lines.append(f"# {target}")
                lines.append(f"make {target}")
            any_commands = True

        justfile = findings.get("justfile_recipes", {})
        if justfile and isinstance(justfile, dict):
            if any_commands:
                lines.append("")
            for recipe in justfile:
                lines.append(f"just {recipe}")
            any_commands = True

        docker = findings.get("docker_commands", {})
        if docker and isinstance(docker, dict):
            if any_commands:
                lines.append("")
            for label, cmd in docker.items():
                lines.append(f"# {label}")
                lines.append(cmd)
            any_commands = True

        lines.append("```")

        if not any_commands:
            return ""

        lines.append("")
        return "\n".join(lines)
