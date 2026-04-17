"""Reality verifier — cross-checks CLAUDE.md claims against the filesystem.

Where the `audit` command scores structure (sections, code blocks, bold bullets),
`verify` scores *truth*: do the files, deps, and version numbers claimed in the
CLAUDE.md actually match what's on disk?
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

_CLAIM_FILE_PATH = re.compile(
    r"""(?x)
    (?:^|[\s│├└─`(])
    (?P<path>
        (?:[\w\-]+/){1,}[\w\-]+\.(?:py|js|ts|tsx|jsx|md|toml|yml|yaml|json|sh|rs|go|sql|html|css)
    )
    """,
)

_VERSION_LINE = re.compile(
    r"""(?mi)^\s*[-*]\s*\*\*version\*\*\s*:\s*v?(?P<version>\d+\.\d+(?:\.\d+)?)""",
)

_DEP_LIST_BLOCK = re.compile(
    r"""(?is)^##\s+Dependencies\b(?P<body>.*?)(?=^##\s|\Z)""",
    re.MULTILINE,
)

_BULLET_DEP = re.compile(
    r"""(?m)^[ \t]*[-*][ \t]+(?:\*\*)?(?P<dep>[\w\-\[\]\.]+)(?:\*\*)?(?:[ \t]*[:—–]|\s*$)""",
)


@dataclass
class RealityFinding:
    severity: str  # "error" | "warning" | "info"
    category: str  # "missing_file" | "unknown_dep" | "version_mismatch"
    message: str
    claim: str
    suggestion: str = ""


@dataclass
class RealityReport:
    checks_run: int = 0
    checks_passed: int = 0
    findings: list[RealityFinding] = field(default_factory=list)

    @property
    def score(self) -> int:
        if self.checks_run == 0:
            return 0
        return round(100 * self.checks_passed / self.checks_run)


def _extract_claimed_files(content: str) -> list[str]:
    """Pull file paths from Architecture / tree blocks and prose."""
    paths: set[str] = set()
    for match in _CLAIM_FILE_PATH.finditer(content):
        path = match.group("path")
        # Strip trailing punctuation and descriptive text.
        path = path.rstrip(")`,.")
        if path.startswith(("http://", "https://")):
            continue
        paths.add(path)
    return sorted(paths)


def _extract_claimed_version(content: str) -> str | None:
    match = _VERSION_LINE.search(content)
    return match.group("version") if match else None


def _extract_claimed_deps(content: str) -> list[str]:
    """Pull dependency names from the Dependencies section."""
    block = _DEP_LIST_BLOCK.search(content)
    if not block:
        return []
    body = block.group("body")
    deps: set[str] = set()
    for match in _BULLET_DEP.finditer(body):
        dep = match.group("dep").strip().lower()
        # Reject obvious non-deps: section-ish names, paths, URLs.
        if not dep or dep in {"core", "runtime", "dev", "cli", "server", "prod", "optional"}:
            continue
        if "/" in dep or "." in dep.replace("-", "") and not re.match(r"^[\w\-]+$", dep):
            continue
        # Strip extras: "pytest[cov]" -> "pytest"
        dep = re.sub(r"\[.*?\]", "", dep)
        deps.add(dep)
    return sorted(deps)


def _project_version(project_root: Path) -> str | None:
    pyproject = project_root / "pyproject.toml"
    if pyproject.is_file():
        try:
            data = tomllib.loads(pyproject.read_text())
        except tomllib.TOMLDecodeError:
            return None
        version = data.get("project", {}).get("version")
        if isinstance(version, str):
            return version
    package_json = project_root / "package.json"
    if package_json.is_file():
        try:
            data = json.loads(package_json.read_text())
        except json.JSONDecodeError:
            return None
        version = data.get("version")
        if isinstance(version, str):
            return version
    return None


def _project_deps(project_root: Path) -> set[str]:
    """Return dependency names from pyproject.toml and/or package.json."""
    deps: set[str] = set()
    pyproject = project_root / "pyproject.toml"
    if pyproject.is_file():
        try:
            data = tomllib.loads(pyproject.read_text())
        except tomllib.TOMLDecodeError:
            data = {}
        project = data.get("project", {})
        for spec in project.get("dependencies", []):
            deps.add(_dep_name(spec))
        optional = project.get("optional-dependencies", {})
        for group in optional.values():
            for spec in group:
                deps.add(_dep_name(spec))

    package_json = project_root / "package.json"
    if package_json.is_file():
        try:
            data = json.loads(package_json.read_text())
        except json.JSONDecodeError:
            data = {}
        for key in ("dependencies", "devDependencies", "peerDependencies"):
            for name in (data.get(key) or {}):
                deps.add(name.lower())

    return deps


def _dep_name(spec: str) -> str:
    """Strip version constraints: 'typer>=0.9.0' -> 'typer'."""
    spec = spec.strip().lower()
    return re.split(r"[<>=!~\[;\s]", spec, maxsplit=1)[0]


def verify(content: str, project_root: Path) -> RealityReport:
    """Cross-check CLAUDE.md claims against reality."""
    report = RealityReport()

    # 1. Files: every path mentioned in prose/architecture should exist.
    for claim in _extract_claimed_files(content):
        report.checks_run += 1
        candidate = project_root / claim
        if candidate.exists():
            report.checks_passed += 1
            continue
        # Tolerate "path/" directory notation matching a file.
        stripped = claim.rstrip("/")
        if (project_root / stripped).exists():
            report.checks_passed += 1
            continue
        report.findings.append(
            RealityFinding(
                severity="warning",
                category="missing_file",
                message=f"Claimed file not found: {claim}",
                claim=claim,
                suggestion=f"Remove reference or update path ({claim})",
            )
        )

    # 2. Version: must match pyproject/package.json if declared.
    claimed_version = _extract_claimed_version(content)
    actual_version = _project_version(project_root)
    if claimed_version and actual_version:
        report.checks_run += 1
        if claimed_version == actual_version:
            report.checks_passed += 1
        else:
            report.findings.append(
                RealityFinding(
                    severity="error",
                    category="version_mismatch",
                    message=f"CLAUDE.md says v{claimed_version}, project is v{actual_version}",
                    claim=claimed_version,
                    suggestion=f"Update Current State → Version to {actual_version}",
                )
            )

    # 3. Deps: named deps must appear in pyproject / package.json.
    claimed_deps = _extract_claimed_deps(content)
    if claimed_deps:
        actual_deps = _project_deps(project_root)
        if actual_deps:  # Only run if the project actually declares deps.
            for dep in claimed_deps:
                report.checks_run += 1
                if dep in actual_deps:
                    report.checks_passed += 1
                else:
                    report.findings.append(
                        RealityFinding(
                            severity="warning",
                            category="unknown_dep",
                            message=f"Dependency '{dep}' not in pyproject/package.json",
                            claim=dep,
                            suggestion=f"Remove '{dep}' from Dependencies or add to manifest",
                        )
                    )

    return report
