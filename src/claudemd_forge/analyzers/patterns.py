"""Coding convention and style pattern analyzer."""

from __future__ import annotations

import logging
import re

from claudemd_forge.config import LANGUAGE_EXTENSIONS
from claudemd_forge.models import AnalysisResult, ForgeConfig, ProjectStructure

logger = logging.getLogger(__name__)

_MAX_SAMPLE_FILES = 50


class PatternAnalyzer:
    """Detects coding conventions and style patterns from source files."""

    def analyze(self, structure: ProjectStructure, config: ForgeConfig) -> AnalysisResult:
        """Sample source files and detect conventions."""
        findings: dict[str, object] = {}

        # Collect source files (not config/markup), prioritizing primary language.
        source_files = [f for f in structure.files if LANGUAGE_EXTENSIONS.get(f.extension)]
        if structure.primary_language:
            primary = structure.primary_language
            primary_exts = {ext for ext, lang in LANGUAGE_EXTENSIONS.items() if lang == primary}
            primary_files = [f for f in source_files if f.extension in primary_exts]
            other_files = [f for f in source_files if f.extension not in primary_exts]
            sample = (primary_files + other_files)[:_MAX_SAMPLE_FILES]
        else:
            sample = source_files[:_MAX_SAMPLE_FILES]

        if not sample:
            return AnalysisResult(
                category="patterns",
                findings={"note": "No source files found to analyze"},
                confidence=0.0,
                section_content="",
            )

        # Read file contents for analysis.
        contents: list[tuple[str, str]] = []  # (extension, content)
        for fi in sample:
            full_path = structure.root / fi.path
            try:
                text = full_path.read_text(errors="replace")
                contents.append((fi.extension, text))
            except OSError:
                continue

        if not contents:
            return AnalysisResult(
                category="patterns",
                findings={"note": "Could not read any source files"},
                confidence=0.0,
                section_content="",
            )

        py_contents = [(e, c) for e, c in contents if e in (".py", ".pyi")]
        js_ts_contents = [(e, c) for e, c in contents if e in (".js", ".jsx", ".ts", ".tsx")]

        findings["naming"] = self._detect_naming(
            contents, structure.primary_language, py_contents, js_ts_contents
        )
        findings["quote_style"] = self._detect_quote_style(py_contents or js_ts_contents)
        findings["type_hints"] = self._detect_type_hints(py_contents)
        findings["docstring_style"] = self._detect_docstring_style(py_contents)
        findings["import_style"] = self._detect_import_style(py_contents)
        findings["path_usage"] = self._detect_path_usage(py_contents)
        findings["semicolons"] = self._detect_semicolons(js_ts_contents)
        findings["line_length_p95"] = self._detect_line_length(contents)
        findings["trailing_commas"] = self._detect_trailing_commas(contents)
        findings["error_handling"] = self._detect_error_handling(contents)

        confidence = min(1.0, len(contents) / _MAX_SAMPLE_FILES)
        section = self._render_section(findings, structure.primary_language)

        return AnalysisResult(
            category="patterns",
            findings=findings,
            confidence=confidence,
            section_content=section,
        )

    def _detect_naming(
        self,
        contents: list[tuple[str, str]],
        primary_language: str | None = None,
        py_contents: list[tuple[str, str]] | None = None,
        js_ts_contents: list[tuple[str, str]] | None = None,
    ) -> str:
        """Detect dominant naming convention, weighted by primary language."""
        # When primary language is known, only analyze its files.
        if primary_language in ("Python", "Rust") and py_contents:
            target = py_contents
        elif primary_language in ("TypeScript", "JavaScript") and js_ts_contents:
            target = js_ts_contents
        else:
            target = contents

        snake = 0
        camel = 0
        for _, text in target:
            snake += len(re.findall(r"\bdef [a-z][a-z0-9_]+\(", text))
            snake += len(re.findall(r"\bfn [a-z][a-z0-9_]+\(", text))
            camel += len(re.findall(r"\bfunction [a-z][a-zA-Z0-9]+\(", text))
            camel += len(re.findall(r"\bconst [a-z][a-zA-Z0-9]+ =", text))
        if snake > camel:
            return "snake_case"
        elif camel > snake:
            return "camelCase"
        return "mixed"

    def _detect_quote_style(self, contents: list[tuple[str, str]]) -> str:
        """Detect single vs double quote preference."""
        single = 0
        double = 0
        for _, text in contents:
            # Count string literals (simple heuristic).
            single += len(re.findall(r"(?<![\"\\])'[^']*'", text))
            double += len(re.findall(r'(?<![\'\\])"[^"]*"', text))
        if double > single * 1.5:
            return "double"
        elif single > double * 1.5:
            return "single"
        return "mixed"

    def _detect_type_hints(self, py_contents: list[tuple[str, str]]) -> str:
        """Detect if Python type hints are used."""
        if not py_contents:
            return "n/a"
        hints = 0
        defs = 0
        for _, text in py_contents:
            defs += len(re.findall(r"\bdef \w+\(", text))
            hints += len(re.findall(r"\bdef \w+\([^)]*:[^)]*\)", text))
            hints += len(re.findall(r"-> \w", text))
        if defs == 0:
            return "n/a"
        ratio = hints / max(defs, 1)
        if ratio > 0.5:
            return "present"
        elif ratio > 0.1:
            return "partial"
        return "absent"

    def _detect_docstring_style(self, py_contents: list[tuple[str, str]]) -> str:
        """Detect docstring style: Google, NumPy, Sphinx, or none."""
        if not py_contents:
            return "none"
        google = 0
        numpy = 0
        sphinx = 0
        for _, text in py_contents:
            google += len(re.findall(r"^\s+(?:Args|Returns|Raises|Example):", text, re.MULTILINE))
            numpy += len(re.findall(r"^\s+(?:Parameters|Returns)\s*\n\s+-+", text, re.MULTILINE))
            sphinx += len(re.findall(r"^\s+:param\s", text, re.MULTILINE))

        if google > numpy and google > sphinx and google > 0:
            return "google"
        elif numpy > google and numpy > sphinx and numpy > 0:
            return "numpy"
        elif sphinx > google and sphinx > numpy and sphinx > 0:
            return "sphinx"
        return "none"

    def _detect_import_style(self, py_contents: list[tuple[str, str]]) -> str:
        """Detect absolute vs relative imports in Python."""
        if not py_contents:
            return "n/a"
        absolute = 0
        relative = 0
        for _, text in py_contents:
            absolute += len(re.findall(r"^from [a-zA-Z]", text, re.MULTILINE))
            relative += len(re.findall(r"^from \.", text, re.MULTILINE))
        if absolute > relative * 2:
            return "absolute"
        elif relative > absolute * 2:
            return "relative"
        return "mixed"

    def _detect_path_usage(self, py_contents: list[tuple[str, str]]) -> str:
        """Detect pathlib vs os.path usage."""
        if not py_contents:
            return "n/a"
        pathlib_count = 0
        ospath_count = 0
        for _, text in py_contents:
            pathlib_count += len(re.findall(r"\bPath\(", text))
            pathlib_count += len(re.findall(r"from pathlib", text))
            ospath_count += len(re.findall(r"\bos\.path\.", text))
        if pathlib_count > ospath_count:
            return "pathlib"
        elif ospath_count > pathlib_count:
            return "os.path"
        return "mixed"

    def _detect_semicolons(self, js_ts_contents: list[tuple[str, str]]) -> str:
        """Detect semicolon usage in JS/TS."""
        if not js_ts_contents:
            return "n/a"
        with_semi = 0
        without_semi = 0
        for _, text in js_ts_contents:
            for line in text.splitlines():
                stripped = line.rstrip()
                if stripped and not stripped.startswith(("//", "/*", "*", "import", "export")):
                    if stripped.endswith(";"):
                        with_semi += 1
                    elif stripped.endswith(("{", "}", "(", ")", ",")):
                        continue  # structural
                    else:
                        without_semi += 1
        if with_semi > without_semi * 2:
            return "required"
        elif without_semi > with_semi * 2:
            return "omitted"
        return "mixed"

    def _detect_line_length(self, contents: list[tuple[str, str]]) -> int:
        """Measure 95th percentile line length."""
        lengths: list[int] = []
        for _, text in contents:
            for line in text.splitlines():
                lengths.append(len(line))
        if not lengths:
            return 0
        lengths.sort()
        idx = int(len(lengths) * 0.95)
        return lengths[min(idx, len(lengths) - 1)]

    def _detect_trailing_commas(self, contents: list[tuple[str, str]]) -> str:
        """Detect trailing comma usage."""
        trailing = 0
        no_trailing = 0
        for _, text in contents:
            # Look for closing brackets preceded by comma.
            trailing += len(re.findall(r",\s*[\]\)\}]", text))
            # Look for closing brackets preceded by non-comma content.
            no_trailing += len(re.findall(r"[^,\s]\s*[\]\)\}]", text))
        if trailing > no_trailing:
            return "yes"
        elif no_trailing > trailing:
            return "no"
        return "mixed"

    def _detect_error_handling(self, contents: list[tuple[str, str]]) -> dict[str, object]:
        """Detect error handling patterns."""
        try_except = 0
        custom_exceptions = False
        for _, text in contents:
            try_except += len(re.findall(r"\btry:", text))
            if re.search(r"class \w+(?:Error|Exception)\(", text):
                custom_exceptions = True
        return {"try_except_count": try_except, "custom_exceptions": custom_exceptions}

    def _render_section(self, findings: dict[str, object], primary_lang: str | None) -> str:
        """Render coding standards section as markdown."""
        lines: list[str] = ["## Coding Standards", ""]

        naming = findings.get("naming", "mixed")
        lines.append(f"- **Naming**: {naming}")

        quotes = findings.get("quote_style", "mixed")
        if quotes != "mixed":
            lines.append(f"- **Quote Style**: {quotes} quotes")

        hints = findings.get("type_hints")
        if hints and hints != "n/a":
            lines.append(f"- **Type Hints**: {hints}")

        docstrings = findings.get("docstring_style")
        if docstrings and docstrings != "none":
            lines.append(f"- **Docstrings**: {docstrings} style")

        imports = findings.get("import_style")
        if imports and imports != "n/a":
            lines.append(f"- **Imports**: {imports}")

        paths = findings.get("path_usage")
        if paths and paths != "n/a":
            lines.append(f"- **Path Handling**: {paths}")

        semis = findings.get("semicolons")
        if semis and semis != "n/a":
            lines.append(f"- **Semicolons**: {semis}")

        line_len = findings.get("line_length_p95", 0)
        if line_len:
            lines.append(f"- **Line Length (p95)**: {line_len} characters")

        err = findings.get("error_handling", {})
        if isinstance(err, dict) and err.get("custom_exceptions"):
            lines.append("- **Error Handling**: Custom exception classes present")

        lines.append("")
        return "\n".join(lines)
