# Prompt 03 — Analyzers

## Context
You are building AnchorMD. Read CLAUDE.md for full context. Prompts 01-02 are complete — models, config, scanner exist and pass tests.

## Task
Build the four analyzers that extract intelligence from the scanned codebase. Each analyzer takes a `ProjectStructure` and `ForgeConfig`, returns an `AnalysisResult`.

## Steps

### 1. Language Analyzer (`src/anchormd/analyzers/language.py`)

```python
class LanguageAnalyzer:
    """Detects languages, frameworks, toolchains, and package managers."""

    def analyze(self, structure: ProjectStructure, config: ForgeConfig) -> AnalysisResult:
        """Detect everything about the project's tech stack."""
```

Detects:
- **Languages**: From file extensions (already in ProjectStructure, but refine)
- **Frameworks**: Check FRAMEWORK_INDICATORS from config
  - Read package.json for JS/TS deps (react, vue, angular, express, next, svelte)
  - Read pyproject.toml/requirements.txt for Python deps (fastapi, django, flask, pytest)
  - Read Cargo.toml for Rust crates
  - Read go.mod for Go modules
- **Package managers**: npm/yarn/pnpm/bun (check lockfiles), pip/uv/poetry, cargo
- **Toolchains**: Detect linters (eslint, ruff, flake8), formatters (prettier, black), type checkers (mypy, tsc)
- **Runtime**: Detect Docker, docker-compose, Makefile, justfile
- **CI/CD**: Detect .github/workflows, .gitlab-ci.yml, Jenkinsfile

Output `section_content`: Markdown section describing the tech stack for CLAUDE.md, e.g.:
```markdown
## Tech Stack
- **Language**: Python 3.11, TypeScript
- **Framework**: FastAPI
- **Package Manager**: uv
- **Linting**: ruff
- **Testing**: pytest
- **CI**: GitHub Actions
```

### 2. Pattern Analyzer (`src/anchormd/analyzers/patterns.py`)

```python
class PatternAnalyzer:
    """Detects coding conventions and style patterns from source files."""

    def analyze(self, structure: ProjectStructure, config: ForgeConfig) -> AnalysisResult:
        """Sample source files and detect conventions."""
```

Detects (by sampling up to 20 source files):
- **Import style**: absolute vs relative imports (Python)
- **Naming conventions**: snake_case, camelCase, PascalCase for functions/classes
- **Quote style**: single vs double quotes (Python, JS/TS)
- **Semicolons**: present or absent (JS/TS)
- **Trailing commas**: yes/no
- **Docstring style**: Google, NumPy, Sphinx, or none
- **Type hints**: present or absent (Python)
- **Path usage**: pathlib vs os.path (Python)
- **Error handling**: try/except patterns, custom exceptions present
- **Line length**: measure 95th percentile line length

Implementation: Read a sample of files, use regex patterns to detect each convention. Count occurrences and report the dominant pattern.

Output `section_content`: Markdown for "Coding Standards" section.

### 3. Command Analyzer (`src/anchormd/analyzers/commands.py`)

```python
class CommandAnalyzer:
    """Detects common CLI commands for the project."""

    def analyze(self, structure: ProjectStructure, config: ForgeConfig) -> AnalysisResult:
        """Extract runnable commands from config files."""
```

Detects:
- **package.json scripts**: Parse `scripts` block → common commands
- **Makefile targets**: Parse target names and first line of recipe
- **justfile recipes**: Parse recipe names
- **pyproject.toml scripts**: Parse `[project.scripts]` and `[tool.pytest]`
- **Dockerfile**: Extract CMD/ENTRYPOINT
- **docker-compose.yml**: Extract service commands
- **tox.ini**: Extract test environments
- **GitHub Actions**: Extract workflow trigger commands

Output `section_content`: Markdown for "Common Commands" section with code blocks.

### 4. Domain Analyzer (`src/anchormd/analyzers/domain.py`)

```python
class DomainAnalyzer:
    """Detects domain-specific terminology and jargon."""

    def analyze(self, structure: ProjectStructure, config: ForgeConfig) -> AnalysisResult:
        """Extract domain terms from code and documentation."""
```

Detects:
- **README terms**: Extract capitalized proper nouns, acronyms, repeated technical terms
- **Model/class names**: Extract class names as domain vocabulary
- **Database models**: If ORM detected, extract table/model names
- **API routes**: If web framework, extract endpoint paths as domain concepts
- **Custom types/enums**: Extract enum values as domain terminology
- **Comment keywords**: Extract TODO, FIXME, HACK, NOTE with context

Output `section_content`: Markdown for "Domain Context" section.

### 5. Analyzer Registry (`src/anchormd/analyzers/__init__.py`)

```python
ANALYZERS: list[type] = [
    LanguageAnalyzer,
    PatternAnalyzer,
    CommandAnalyzer,
    DomainAnalyzer,
]

def run_all(structure: ProjectStructure, config: ForgeConfig) -> list[AnalysisResult]:
    """Run all registered analyzers and return results."""
```

### 6. Tests (`tests/test_analyzers.py`)

For each analyzer, create a temp project fixture and verify:
- **Language**: Detects Python from .py files, React from package.json with react dep
- **Patterns**: Detects snake_case in Python files, double quotes, type hints present
- **Commands**: Extracts `test` script from package.json, Makefile targets
- **Domain**: Extracts class names, README terms
- **Registry**: `run_all` returns 4 results, all with valid category names

## Acceptance Criteria
- `pytest tests/test_analyzers.py -v` — all pass
- Each analyzer returns valid `AnalysisResult` with non-empty `section_content`
- Analyzers handle missing files gracefully (no package.json? skip JS detection)
- No file is read more than once across all analyzers (cache in scanner or pass content)
- `ruff check src/anchormd/analyzers/` — clean
