# Prompt 04 — Generators

## Context
You are building AnchorMD. Read CLAUDE.md for full context. Prompts 01-03 are complete — models, scanner, and all four analyzers exist and pass tests.

## Task
Build the generators that compose analyzer results into a complete, polished CLAUDE.md document.

## Steps

### 1. Section Generator (`src/anchormd/generators/sections.py`)

```python
class SectionGenerator:
    """Generates individual CLAUDE.md sections from analysis results."""

    def generate_header(self, project_name: str, description: str = "") -> str:
        """# CLAUDE.md — {project_name}\n\n## Project Overview\n..."""

    def generate_current_state(self, structure: ProjectStructure) -> str:
        """## Current State\n- Phase, version, language, stats"""

    def generate_architecture(self, structure: ProjectStructure) -> str:
        """## Architecture\n```\nproject tree (2 levels deep)\n```"""

    def generate_tech_stack(self, analysis: AnalysisResult) -> str:
        """Use language analyzer's section_content, clean up"""

    def generate_coding_standards(self, analysis: AnalysisResult) -> str:
        """Use pattern analyzer's section_content, enhance with anti-patterns"""

    def generate_commands(self, analysis: AnalysisResult) -> str:
        """Use command analyzer's section_content"""

    def generate_domain_context(self, analysis: AnalysisResult) -> str:
        """Use domain analyzer's section_content"""

    def generate_anti_patterns(self, structure: ProjectStructure, analyses: list[AnalysisResult]) -> str:
        """## Anti-Patterns (Do NOT Do)\nInfer from detected stack."""

    def generate_dependencies(self, analyses: list[AnalysisResult]) -> str:
        """## Dependencies\nList core and dev deps from detected config."""

    def generate_git_conventions(self, structure: ProjectStructure) -> str:
        """## Git Conventions\nDetect from existing commits or suggest defaults."""
```

Key anti-pattern inference rules:
- Python detected → "Do NOT use os.path — use pathlib.Path"
- React detected → "Do NOT use class components — use functional components with hooks"
- TypeScript detected → "Do NOT use `any` type — use proper type definitions"
- FastAPI detected → "Do NOT use synchronous database calls in async endpoints"
- Rust detected → "Do NOT use `.unwrap()` in production code — use proper error handling"
- Docker detected → "Do NOT hardcode secrets — use environment variables"
- Tests detected → "Do NOT skip writing tests for new code"

### 2. Document Composer (`src/anchormd/generators/composer.py`)

```python
class DocumentComposer:
    """Assembles sections into a complete CLAUDE.md document."""

    def __init__(self, config: ForgeConfig): ...

    def compose(
        self,
        structure: ProjectStructure,
        analyses: list[AnalysisResult],
        project_name: str | None = None,
    ) -> str:
        """Compose all sections into final CLAUDE.md content.

        Section ordering follows config.SECTION_ORDER.
        Empty sections are omitted.
        """

    def _clean_output(self, content: str) -> str:
        """Remove excessive blank lines, normalize heading levels,
        ensure single trailing newline."""

    def _estimate_quality_score(self, content: str) -> int:
        """Score 0-100 based on section coverage and content depth."""
```

Composition rules:
- Sections appear in `SECTION_ORDER` from config.py
- Empty/None sections are silently omitted
- Each section separated by exactly one blank line
- No duplicate headings
- Total output should be 80-300 lines for a typical project
- Quality score factors: number of sections present, specificity of content, presence of code blocks

### 3. Tests (`tests/test_generators.py`)

- Test: `SectionGenerator.generate_header` produces valid markdown with project name
- Test: `generate_architecture` produces a code-fenced tree
- Test: `generate_anti_patterns` produces Python-specific anti-patterns for Python project
- Test: `generate_anti_patterns` produces React-specific anti-patterns for React project
- Test: `DocumentComposer.compose` produces non-empty string with expected sections
- Test: `compose` omits empty sections
- Test: `_clean_output` normalizes excessive blank lines
- Test: `_estimate_quality_score` returns 0-100 range
- Test: Full pipeline — scanner → analyzers → composer produces valid CLAUDE.md

## Acceptance Criteria
- `pytest tests/test_generators.py -v` — all pass
- Running full pipeline on `anchormd` itself produces a sensible CLAUDE.md
- Output is clean markdown that renders correctly
- Quality score for self-generated CLAUDE.md is > 60
- `ruff check src/anchormd/generators/` — clean
