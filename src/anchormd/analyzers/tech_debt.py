"""Technical debt analyzer — scans source code for debt signals."""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field

from anchormd.config import LANGUAGE_EXTENSIONS
from anchormd.models import AnalysisResult, ForgeConfig, ProjectStructure

logger = logging.getLogger(__name__)

_MAX_SAMPLE_FILES = 100

# Thresholds
_GOD_FILE_LINES = 500
_GOD_FUNCTION_LINES = 50
_DEEP_NESTING_LEVEL = 5
_MAGIC_NUMBER_MIN = 2  # ignore 0, 1


@dataclass
class DebtSignal:
    """A single technical debt signal found in the codebase."""

    category: str
    severity: str  # "critical", "high", "medium", "low"
    file: str
    line: int | None
    message: str


@dataclass
class DebtSummary:
    """Aggregated technical debt findings."""

    signals: list[DebtSignal] = field(default_factory=list)
    category_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    score: int = 100  # starts at 100, deductions applied

    def add(self, signal: DebtSignal) -> None:
        self.signals.append(signal)
        self.category_counts[signal.category] += 1


# Severity weights for scoring
_SEVERITY_WEIGHTS = {
    "critical": 10,
    "high": 5,
    "medium": 2,
    "low": 1,
}

# Debt comment patterns
_DEBT_COMMENT_PATTERNS = [
    (re.compile(r"\bTODO\b", re.IGNORECASE), "TODO"),
    (re.compile(r"\bFIXME\b", re.IGNORECASE), "FIXME"),
    (re.compile(r"\bHACK\b", re.IGNORECASE), "HACK"),
    (re.compile(r"\bXXX\b"), "XXX"),
    (re.compile(r"\bWORKAROUND\b", re.IGNORECASE), "WORKAROUND"),
    (re.compile(r"\bTEMP\b"), "TEMP"),
    (re.compile(r"\bKLUDGE\b", re.IGNORECASE), "KLUDGE"),
]

# Patterns that look like hardcoded secrets
_SECRET_PATTERNS = [
    re.compile(r"""['"](?:sk|pk|api|secret|token|password|key)[-_][a-zA-Z0-9]{16,}['"]"""),
    re.compile(r"""['"](?:ghp|gho|ghu|ghs|ghr)_[a-zA-Z0-9]{30,}['"]"""),
    re.compile(r"""['"]AKIA[A-Z0-9]{16}['"]"""),
]

# Python bare except
_BARE_EXCEPT_PY = re.compile(r"^\s*except\s*:", re.MULTILINE)
# Python catch-all except Exception
_CATCH_ALL_PY = re.compile(r"^\s*except\s+(?:Exception|BaseException)\s*:", re.MULTILINE)
# Print debugging
_PRINT_DEBUG_PY = re.compile(r"^\s*print\s*\(", re.MULTILINE)
# console.log
_CONSOLE_LOG_JS = re.compile(r"\bconsole\.log\s*\(", re.MULTILINE)
# Magic numbers in assignments/comparisons (not 0, 1, -1, 2)
_MAGIC_NUMBER = re.compile(r"(?:==|!=|<=|>=|<|>|=)\s*(\d+\.?\d*)")
# Python function definition with line counting
_PY_FUNC_DEF = re.compile(r"^(\s*)def\s+(\w+)\s*\(", re.MULTILINE)
# JS/TS function definition
_JS_FUNC_DEF = re.compile(
    r"^(\s*)(?:(?:async\s+)?function\s+(\w+)|(?:const|let)\s+(\w+)\s*=\s*(?:async\s+)?\()",
    re.MULTILINE,
)
# Rust function definition
_RS_FUNC_DEF = re.compile(r"^(\s*)(?:pub\s+)?(?:async\s+)?fn\s+(\w+)", re.MULTILINE)


class TechDebtAnalyzer:
    """Scans source code for technical debt signals."""

    def analyze(self, structure: ProjectStructure, config: ForgeConfig) -> AnalysisResult:
        """Scan source files and detect technical debt."""
        summary = DebtSummary()

        source_files = [f for f in structure.files if LANGUAGE_EXTENSIONS.get(f.extension)]

        # Project-level checks
        self._check_project_hygiene(structure, summary)

        # Sample source files for code-level checks
        if structure.primary_language:
            primary = structure.primary_language
            primary_exts = {ext for ext, lang in LANGUAGE_EXTENSIONS.items() if lang == primary}
            primary_files = [f for f in source_files if f.extension in primary_exts]
            other_files = [f for f in source_files if f.extension not in primary_exts]
            sample = (primary_files + other_files)[:_MAX_SAMPLE_FILES]
        else:
            sample = source_files[:_MAX_SAMPLE_FILES]

        # God files check (uses metadata, no file read needed)
        for fi in source_files:
            if fi.line_count and fi.line_count > _GOD_FILE_LINES:
                summary.add(
                    DebtSignal(
                        category="complexity",
                        severity="high",
                        file=str(fi.path),
                        line=None,
                        message=f"God file: {fi.line_count} lines (>{_GOD_FILE_LINES})",
                    )
                )

        # Code-level checks on sampled files
        for fi in sample:
            full_path = structure.root / fi.path
            try:
                text = full_path.read_text(errors="replace")
            except OSError:
                continue

            filepath = str(fi.path)
            is_test = self._is_test_file(filepath)

            self._check_debt_comments(text, filepath, summary)
            self._check_secrets(text, filepath, summary)

            if not is_test:
                self._check_error_handling(text, filepath, fi.extension, summary)
                self._check_debug_statements(text, filepath, fi.extension, summary)
                self._check_god_functions(text, filepath, fi.extension, summary)
                self._check_deep_nesting(text, filepath, summary)

        # Calculate score
        summary.score = self._calculate_score(summary)

        # Build findings dict for AnalysisResult
        findings = {
            "score": summary.score,
            "total_signals": len(summary.signals),
            "categories": dict(summary.category_counts),
            "critical_count": sum(1 for s in summary.signals if s.severity == "critical"),
            "high_count": sum(1 for s in summary.signals if s.severity == "high"),
            "medium_count": sum(1 for s in summary.signals if s.severity == "medium"),
            "low_count": sum(1 for s in summary.signals if s.severity == "low"),
            "signals": [
                {
                    "category": s.category,
                    "severity": s.severity,
                    "file": s.file,
                    "line": s.line,
                    "message": s.message,
                }
                for s in summary.signals
            ],
        }

        confidence = min(1.0, len(sample) / _MAX_SAMPLE_FILES)
        section = self._render_section(summary)

        return AnalysisResult(
            category="tech_debt",
            findings=findings,
            confidence=confidence,
            section_content=section,
        )

    def _is_test_file(self, filepath: str) -> bool:
        """Check if a file is a test file."""
        parts = filepath.lower().replace("\\", "/")
        return (
            "test" in parts.split("/")
            or "tests" in parts.split("/")
            or parts.endswith("_test.py")
            or parts.startswith("test_")
            or parts.split("/")[-1].startswith("test_")
            or parts.endswith(".test.ts")
            or parts.endswith(".test.tsx")
            or parts.endswith(".test.js")
            or parts.endswith(".spec.ts")
            or parts.endswith(".spec.js")
        )

    def _check_project_hygiene(self, structure: ProjectStructure, summary: DebtSummary) -> None:
        """Check project-level debt signals."""
        dir_names = {d.name for d in structure.directories}
        file_names = {f.path.name for f in structure.files}
        file_paths = {str(f.path) for f in structure.files}

        # No tests
        has_tests = (
            "tests" in dir_names
            or "test" in dir_names
            or any(self._is_test_file(str(f.path)) for f in structure.files)
        )
        if not has_tests and structure.total_files > 5:
            summary.add(
                DebtSignal(
                    category="testing",
                    severity="critical",
                    file="<project>",
                    line=None,
                    message="No test directory or test files found",
                )
            )

        # No CI/CD
        has_ci = any(
            p
            for p in file_paths
            if ".github/workflows" in p
            or ".gitlab-ci" in p
            or "Jenkinsfile" in str(p)
            or ".circleci" in p
        )
        if not has_ci and structure.total_files > 10:
            summary.add(
                DebtSignal(
                    category="infrastructure",
                    severity="medium",
                    file="<project>",
                    line=None,
                    message="No CI/CD configuration found",
                )
            )

        # No linter config
        linter_files = {
            ".eslintrc",
            ".eslintrc.js",
            ".eslintrc.json",
            ".eslintrc.yml",
            "eslint.config.js",
            "eslint.config.mjs",
            ".flake8",
            ".pylintrc",
            "ruff.toml",
            ".clippy.toml",
            "biome.json",
        }
        # Also check pyproject.toml for [tool.ruff] etc.
        has_linter = bool(linter_files & file_names)
        if not has_linter:
            # Check pyproject.toml for embedded config
            for f in structure.files:
                if f.path.name == "pyproject.toml":
                    try:
                        text = (structure.root / f.path).read_text(errors="replace")
                        if "[tool.ruff" in text or "[tool.pylint" in text or "[tool.flake8" in text:
                            has_linter = True
                    except OSError:
                        pass
        if not has_linter and structure.total_files > 5:
            summary.add(
                DebtSignal(
                    category="infrastructure",
                    severity="medium",
                    file="<project>",
                    line=None,
                    message="No linter configuration found",
                )
            )

        # No .gitignore
        if ".gitignore" not in file_names and structure.total_files > 3:
            summary.add(
                DebtSignal(
                    category="infrastructure",
                    severity="low",
                    file="<project>",
                    line=None,
                    message="No .gitignore file",
                )
            )

    def _check_debt_comments(self, text: str, filepath: str, summary: DebtSummary) -> None:
        """Find TODO/FIXME/HACK comments."""
        for i, line in enumerate(text.splitlines(), 1):
            for pattern, label in _DEBT_COMMENT_PATTERNS:
                if pattern.search(line):
                    severity = "high" if label in ("FIXME", "HACK", "KLUDGE") else "medium"
                    summary.add(
                        DebtSignal(
                            category="debt_markers",
                            severity=severity,
                            file=filepath,
                            line=i,
                            message=f"{label}: {line.strip()[:120]}",
                        )
                    )
                    break  # one match per line

    def _check_secrets(self, text: str, filepath: str, summary: DebtSummary) -> None:
        """Detect potential hardcoded secrets."""
        for i, line in enumerate(text.splitlines(), 1):
            for pattern in _SECRET_PATTERNS:
                if pattern.search(line):
                    summary.add(
                        DebtSignal(
                            category="security",
                            severity="critical",
                            file=filepath,
                            line=i,
                            message="Potential hardcoded secret/credential",
                        )
                    )
                    break

    def _check_error_handling(
        self, text: str, filepath: str, ext: str, summary: DebtSummary
    ) -> None:
        """Check for bare excepts and overly broad exception handling."""
        if ext not in (".py", ".pyi"):
            return

        for match in _BARE_EXCEPT_PY.finditer(text):
            line_num = text[: match.start()].count("\n") + 1
            summary.add(
                DebtSignal(
                    category="error_handling",
                    severity="high",
                    file=filepath,
                    line=line_num,
                    message=(
                        "Bare `except:` catches all exceptions "
                        "including SystemExit/KeyboardInterrupt"
                    ),
                )
            )

        for match in _CATCH_ALL_PY.finditer(text):
            line_num = text[: match.start()].count("\n") + 1
            summary.add(
                DebtSignal(
                    category="error_handling",
                    severity="medium",
                    file=filepath,
                    line=line_num,
                    message="Broad `except Exception` — consider catching specific exceptions",
                )
            )

    def _check_debug_statements(
        self, text: str, filepath: str, ext: str, summary: DebtSummary
    ) -> None:
        """Detect print debugging and console.log in production code."""
        if ext in (".py", ".pyi"):
            for match in _PRINT_DEBUG_PY.finditer(text):
                line_num = text[: match.start()].count("\n") + 1
                summary.add(
                    DebtSignal(
                        category="code_quality",
                        severity="low",
                        file=filepath,
                        line=line_num,
                        message="print() in production code — use logging module",
                    )
                )
        elif ext in (".js", ".jsx", ".ts", ".tsx"):
            for match in _CONSOLE_LOG_JS.finditer(text):
                line_num = text[: match.start()].count("\n") + 1
                summary.add(
                    DebtSignal(
                        category="code_quality",
                        severity="low",
                        file=filepath,
                        line=line_num,
                        message="console.log() in production code",
                    )
                )

    def _check_god_functions(
        self, text: str, filepath: str, ext: str, summary: DebtSummary
    ) -> None:
        """Detect functions that are too long."""
        if ext in (".py", ".pyi"):
            pattern = _PY_FUNC_DEF
        elif ext in (".js", ".jsx", ".ts", ".tsx"):
            pattern = _JS_FUNC_DEF
        elif ext == ".rs":
            pattern = _RS_FUNC_DEF
        else:
            return

        lines = text.splitlines()
        matches = list(pattern.finditer(text))

        for i, match in enumerate(matches):
            func_name = match.group(2) or (
                match.group(3) if match.lastindex and match.lastindex >= 3 else "anonymous"
            )
            func_start_line = text[: match.start()].count("\n")

            # Find function end: next function at same or lesser indent, or EOF
            indent_level = len(match.group(1))
            func_end_line = len(lines)

            if i + 1 < len(matches):
                next_match = matches[i + 1]
                next_indent = len(next_match.group(1))
                if next_indent <= indent_level:
                    func_end_line = text[: next_match.start()].count("\n")

            func_length = func_end_line - func_start_line
            if func_length > _GOD_FUNCTION_LINES:
                summary.add(
                    DebtSignal(
                        category="complexity",
                        severity="medium",
                        file=filepath,
                        line=func_start_line + 1,
                        message=(
                            f"Function `{func_name}` is {func_length} lines "
                            f"(>{_GOD_FUNCTION_LINES})"
                        ),
                    )
                )

    def _check_deep_nesting(self, text: str, filepath: str, summary: DebtSummary) -> None:
        """Detect deeply nested code blocks."""
        max_indent = 0
        max_indent_line = 0
        for i, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            # Count leading spaces (normalize tabs to 4 spaces)
            expanded = line.expandtabs(4)
            indent = len(expanded) - len(expanded.lstrip())
            level = indent // 4
            if level > max_indent:
                max_indent = level
                max_indent_line = i

        if max_indent >= _DEEP_NESTING_LEVEL:
            summary.add(
                DebtSignal(
                    category="complexity",
                    severity="medium",
                    file=filepath,
                    line=max_indent_line,
                    message=f"Deep nesting: {max_indent} levels (>={_DEEP_NESTING_LEVEL})",
                )
            )

    def _calculate_score(self, summary: DebtSummary) -> int:
        """Calculate 0-100 debt score. 100 = no debt, 0 = critical debt."""
        score = 100
        for signal in summary.signals:
            score -= _SEVERITY_WEIGHTS.get(signal.severity, 1)
        return max(0, min(100, score))

    def _render_section(self, summary: DebtSummary) -> str:
        """Render technical debt section for CLAUDE.md."""
        if not summary.signals:
            return ""

        lines: list[str] = ["## Technical Debt", ""]
        lines.append(f"**Debt Score**: {summary.score}/100")
        lines.append(f"**Total Signals**: {len(summary.signals)}")
        lines.append("")

        if summary.category_counts:
            lines.append("### Categories")
            for cat, count in sorted(summary.category_counts.items(), key=lambda x: -x[1]):
                label = cat.replace("_", " ").title()
                lines.append(f"- **{label}**: {count} issues")
            lines.append("")

        # Top priority items (critical + high only)
        priority = [s for s in summary.signals if s.severity in ("critical", "high")]
        if priority:
            lines.append("### Priority Items")
            for signal in priority[:10]:  # cap at 10
                loc = f"`{signal.file}"
                if signal.line:
                    loc += f":{signal.line}"
                loc += "`"
                lines.append(f"- [{signal.severity.upper()}] {loc} — {signal.message}")
            if len(priority) > 10:
                lines.append(f"- ... and {len(priority) - 10} more")
            lines.append("")

        return "\n".join(lines)
