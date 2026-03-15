# Prompt 01 — Foundation

## Context
You are building AnchorMD, a Python CLI tool that analyzes codebases and generates optimized CLAUDE.md files for AI coding agents. Read CLAUDE.md first for full project context.

## Task
Set up the project foundation: package config, data models, configuration, and basic structure.

## Steps

1. **Create `pyproject.toml`** with PEP 621 metadata:
   - Name: `anchormd`
   - Version: `0.1.0`
   - Description: "Generate and audit CLAUDE.md files for AI coding agents"
   - Author: AreteDriver
   - License: MIT
   - Python requires: `>=3.11`
   - All dependencies from CLAUDE.md
   - Entry point: `anchormd = "anchormd.cli:app"`
   - Dev dependencies group: pytest, mypy, ruff
   - Ruff config: line-length=100, target-version="py311"

2. **Create `src/anchormd/__init__.py`**:
   - `__version__ = "0.1.0"`
   - `__all__` exports

3. **Create `src/anchormd/models.py`** with Pydantic v2 models:
   ```python
   class FileInfo(BaseModel):
       path: Path
       extension: str
       size_bytes: int
       line_count: int | None = None

   class ProjectStructure(BaseModel):
       root: Path
       files: list[FileInfo]
       directories: list[Path]
       total_files: int
       total_lines: int
       primary_language: str | None = None
       languages: dict[str, int]  # language -> file count

   class AnalysisResult(BaseModel):
       category: str  # e.g., "language", "patterns", "commands", "domain"
       findings: dict[str, Any]
       confidence: float  # 0.0 - 1.0
       section_content: str  # rendered markdown for this section

   class AuditFinding(BaseModel):
       severity: Literal["error", "warning", "info"]
       category: str
       message: str
       suggestion: str | None = None

   class AuditReport(BaseModel):
       score: int  # 0-100
       findings: list[AuditFinding]
       missing_sections: list[str]
       recommendations: list[str]

   class ForgeConfig(BaseModel):
       root_path: Path
       output_path: Path | None = None
       preset: str = "default"
       include_patterns: list[str] = ["*"]
       exclude_patterns: list[str] = Field(default_factory=lambda: [
           "node_modules", ".git", "__pycache__", ".venv", "venv",
           "dist", "build", ".next", "target", ".tox"
       ])
       max_file_size_kb: int = 500
       max_files: int = 5000
   ```

4. **Create `src/anchormd/config.py`**:
   - `DEFAULT_EXCLUDE_DIRS`: list of directories to always skip
   - `LANGUAGE_EXTENSIONS`: dict mapping file extensions to language names
   - `FRAMEWORK_INDICATORS`: dict mapping framework names to detection files
     - e.g., `"react": ["package.json:react", "src/App.tsx", "src/App.jsx"]`
     - `"fastapi": ["requirements.txt:fastapi", "pyproject.toml:fastapi"]`
     - `"django": ["manage.py", "settings.py"]`
     - `"rust": ["Cargo.toml"]`
     - `"nextjs": ["next.config.js", "next.config.ts"]`
   - `SECTION_ORDER`: default ordering of CLAUDE.md sections
   - `BUILTIN_PRESETS`: dict of preset names to config overrides

5. **Create `src/anchormd/exceptions.py`**:
   - `ForgeError(Exception)` — base
   - `ScanError(ForgeError)` — filesystem issues
   - `AnalysisError(ForgeError)` — analysis failures
   - `TemplateError(ForgeError)` — template rendering issues

6. **Create `tests/conftest.py`**:
   - Fixture: `tmp_project` — creates a temp directory with a basic Python project structure
   - Fixture: `tmp_react_project` — creates a temp dir with package.json and React files
   - Fixture: `sample_config` — returns a ForgeConfig with defaults

7. **Create basic tests**:
   - `test_models.py`: Verify all Pydantic models instantiate and validate correctly
   - Test that ForgeConfig defaults are sensible
   - Test that AnalysisResult requires all fields

## Acceptance Criteria
- `uv pip install -e ".[dev]"` succeeds
- `pytest tests/test_models.py -v` passes
- All models round-trip through `.model_dump()` and `.model_validate()`
- `ruff check src/` reports no issues
