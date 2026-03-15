"""Domain-specific terminology and jargon analyzer."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from anchormd.config import LANGUAGE_EXTENSIONS
from anchormd.models import AnalysisResult, ForgeConfig, ProjectStructure

logger = logging.getLogger(__name__)


class DomainAnalyzer:
    """Detects domain-specific terminology and jargon."""

    def analyze(self, structure: ProjectStructure, config: ForgeConfig) -> AnalysisResult:
        """Extract domain terms from code and documentation."""
        findings: dict[str, object] = {}
        root = structure.root

        findings["class_names"] = self._extract_class_names(structure)
        findings["readme_terms"] = self._extract_readme_terms(root)
        findings["api_routes"] = self._extract_api_routes(structure)
        findings["enum_values"] = self._extract_enum_values(structure)
        findings["comment_keywords"] = self._extract_comment_keywords(structure)

        # Confidence based on how much domain info we found.
        item_count = sum(
            len(v) if isinstance(v, (list, dict)) else (1 if v else 0) for v in findings.values()
        )
        confidence = min(1.0, item_count / 20.0)

        section = self._render_section(findings)

        return AnalysisResult(
            category="domain",
            findings=findings,
            confidence=confidence,
            section_content=section,
        )

    def _extract_class_names(self, structure: ProjectStructure) -> list[str]:
        """Extract class names as domain vocabulary."""
        classes: set[str] = set()
        for fi in structure.files:
            if fi.extension not in (".py", ".ts", ".tsx", ".js", ".jsx", ".rs"):
                continue
            full_path = structure.root / fi.path
            try:
                text = full_path.read_text(errors="replace")
            except OSError:
                continue

            # Python/JS/TS classes.
            for match in re.finditer(r"\bclass\s+(\w+)", text):
                name = match.group(1)
                if not name.startswith("_") and len(name) > 2:
                    classes.add(name)

            # Rust structs/enums.
            for match in re.finditer(r"\b(?:struct|enum)\s+(\w+)", text):
                name = match.group(1)
                if len(name) > 2:
                    classes.add(name)

        return sorted(classes)[:30]

    def _extract_readme_terms(self, root: Path) -> list[str]:
        """Extract capitalized proper nouns and acronyms from README."""
        terms: set[str] = set()
        for name in ("README.md", "README.rst", "README.txt", "README"):
            readme = root / name
            if readme.is_file():
                try:
                    text = readme.read_text(errors="replace")
                except OSError:
                    continue

                # Acronyms (2+ uppercase letters).
                for match in re.finditer(r"\b([A-Z]{2,})\b", text):
                    term = match.group(1)
                    if term not in ("README", "TODO", "NOTE", "API", "URL", "HTTP", "CLI"):
                        terms.add(term)

                # Capitalized multi-word terms (potential proper nouns).
                for match in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", text):
                    normalized = " ".join(match.group(1).split())
                    terms.add(normalized)

                break  # Only read first README found.

        return sorted(terms)[:20]

    def _extract_api_routes(self, structure: ProjectStructure) -> list[str]:
        """Extract API endpoint paths from web framework code."""
        routes: set[str] = set()
        for fi in structure.files:
            if fi.extension not in (".py", ".ts", ".js"):
                continue
            full_path = structure.root / fi.path
            try:
                text = full_path.read_text(errors="replace")
            except OSError:
                continue

            # FastAPI/Flask decorators.
            for match in re.finditer(
                r'@(?:app|router)\.\s*(?:get|post|put|patch|delete)\s*\(\s*["\']([^"\']+)',
                text,
            ):
                routes.add(match.group(1))

            # Express-style routes.
            for match in re.finditer(
                r'(?:app|router)\.\s*(?:get|post|put|patch|delete)\s*\(\s*["\']([^"\']+)',
                text,
            ):
                routes.add(match.group(1))

        return sorted(routes)[:30]

    def _extract_enum_values(self, structure: ProjectStructure) -> list[str]:
        """Extract enum values as domain terminology."""
        enums: set[str] = set()
        for fi in structure.files:
            if fi.extension not in (".py", ".ts", ".rs"):
                continue
            full_path = structure.root / fi.path
            try:
                text = full_path.read_text(errors="replace")
            except OSError:
                continue

            # Python enums.
            for match in re.finditer(r"(\w+)\s*=\s*(?:auto\(\)|['\"])", text):
                name = match.group(1)
                if name.isupper() and len(name) > 2:
                    enums.add(name)

            # TypeScript enums.
            for match in re.finditer(r"\benum\s+(\w+)", text):
                enums.add(match.group(1))

            # Rust enums variants.
            in_enum = False
            for line in text.splitlines():
                if re.match(r"\benum\s+\w+", line):
                    in_enum = True
                elif in_enum:
                    variant_match = re.match(r"\s+(\w+)", line)
                    if variant_match and variant_match.group(1)[0].isupper():
                        enums.add(variant_match.group(1))
                    if "}" in line:
                        in_enum = False

        return sorted(enums)[:20]

    def _extract_comment_keywords(self, structure: ProjectStructure) -> list[dict[str, str]]:
        """Extract TODO, FIXME, HACK, NOTE comments with context."""
        keywords: list[dict[str, str]] = []
        for fi in structure.files:
            lang = LANGUAGE_EXTENSIONS.get(fi.extension)
            if not lang:
                continue
            full_path = structure.root / fi.path
            try:
                text = full_path.read_text(errors="replace")
            except OSError:
                continue

            for match in re.finditer(r"#\s*(TODO|FIXME|HACK|NOTE|XXX)[\s:]+(.+)", text):
                keywords.append(
                    {
                        "type": match.group(1),
                        "text": match.group(2).strip()[:100],
                        "file": str(fi.path),
                    }
                )

            # Also check // comments.
            for match in re.finditer(r"//\s*(TODO|FIXME|HACK|NOTE|XXX)[\s:]+(.+)", text):
                keywords.append(
                    {
                        "type": match.group(1),
                        "text": match.group(2).strip()[:100],
                        "file": str(fi.path),
                    }
                )

        return keywords[:30]

    def _render_section(self, findings: dict[str, object]) -> str:
        """Render domain context section as markdown."""
        lines: list[str] = ["## Domain Context", ""]

        classes = findings.get("class_names", [])
        if classes and isinstance(classes, list):
            lines.append("### Key Models/Classes")
            for name in classes[:15]:
                lines.append(f"- `{name}`")
            lines.append("")

        readme_terms = findings.get("readme_terms", [])
        if readme_terms and isinstance(readme_terms, list):
            lines.append("### Domain Terms")
            for term in readme_terms[:10]:
                lines.append(f"- {term}")
            lines.append("")

        routes = findings.get("api_routes", [])
        if routes and isinstance(routes, list):
            lines.append("### API Endpoints")
            for route in routes[:15]:
                lines.append(f"- `{route}`")
            lines.append("")

        enums = findings.get("enum_values", [])
        if enums and isinstance(enums, list) and len(enums) > 0:
            lines.append("### Enums/Constants")
            for val in enums[:10]:
                lines.append(f"- `{val}`")
            lines.append("")

        keywords = findings.get("comment_keywords", [])
        if keywords and isinstance(keywords, list):
            lines.append("### Outstanding Items")
            for kw in keywords[:10]:
                if isinstance(kw, dict):
                    lines.append(f"- **{kw['type']}**: {kw['text']} (`{kw['file']}`)")
            lines.append("")

        # If nothing found, return empty.
        if len(lines) <= 2:
            return ""

        return "\n".join(lines)
