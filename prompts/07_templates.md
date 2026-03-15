# Prompt 07 — Templates & Presets

## Context
You are building AnchorMD. Read CLAUDE.md for full context. Prompts 01-06 are complete — full pipeline, CLI, and auditor working.

## Task
Build the template system with framework-specific presets and Jinja2 rendering. This is the "value add" layer — curated, opinionated templates that save developers from writing generic CLAUDE.md files.

## Steps

### 1. Base Template (`src/anchormd/templates/base.py`)

```python
class BaseTemplate:
    """Base CLAUDE.md template with all available sections."""

    # Section templates as Jinja2 strings
    HEADER = "# CLAUDE.md — {{ project_name }}\n\n{{ description }}"

    PROJECT_OVERVIEW = """## Project Overview
{{ overview_text }}
"""

    CURRENT_STATE = """## Current State
- **Phase**: {{ phase }}
- **Version**: {{ version }}
- **Language**: {{ primary_language }}
- **Files**: {{ total_files }} across {{ language_count }} languages
"""

    ARCHITECTURE = """## Architecture
```
{{ tree }}
```
"""

    # ... etc for each section

    @classmethod
    def get_section_template(cls, section_name: str) -> str:
        """Return Jinja2 template string for a named section."""

    @classmethod
    def render_section(cls, section_name: str, **context) -> str:
        """Render a section template with context variables."""
```

### 2. Framework Presets (`src/anchormd/templates/frameworks.py`)

Each preset extends BaseTemplate with framework-specific defaults:

```python
FRAMEWORK_PRESETS: dict[str, FrameworkPreset] = {
    "python-fastapi": FrameworkPreset(
        name="Python + FastAPI",
        description="FastAPI web application with async patterns",
        coding_standards=[
            "Use async/await for all endpoint handlers",
            "Define request/response models with Pydantic",
            "Use dependency injection for shared resources",
            "Keep route handlers thin — business logic in service layer",
        ],
        anti_patterns=[
            "Do NOT use synchronous database calls in async endpoints",
            "Do NOT use `*` imports",
            "Do NOT put business logic in route handlers",
            "Do NOT use os.path — use pathlib.Path",
            "Do NOT return raw dicts — use Pydantic response models",
        ],
        common_commands={
            "dev server": "uvicorn app.main:app --reload",
            "test": "pytest tests/ -v",
            "lint": "ruff check .",
            "format": "ruff format .",
            "type check": "mypy src/",
        },
    ),

    "react-typescript": FrameworkPreset(
        name="React + TypeScript",
        description="React application with TypeScript",
        coding_standards=[
            "Use functional components with hooks exclusively",
            "Define prop types with TypeScript interfaces, not `any`",
            "Use named exports, not default exports",
            "Keep components under 200 lines — extract sub-components",
            "Co-locate tests with components: `Component.test.tsx`",
        ],
        anti_patterns=[
            "Do NOT use class components",
            "Do NOT use `any` type — define proper interfaces",
            "Do NOT use inline styles — use Tailwind or CSS modules",
            "Do NOT mutate state directly — use immutable patterns",
            "Do NOT use `useEffect` for derived state — use `useMemo`",
        ],
        common_commands={
            "dev": "npm run dev",
            "build": "npm run build",
            "test": "npm test",
            "lint": "npm run lint",
            "type check": "npx tsc --noEmit",
        },
    ),

    "rust": FrameworkPreset(
        name="Rust",
        description="Rust application or library",
        coding_standards=[
            "Use Result<T, E> for fallible operations, not panic",
            "Derive common traits: Debug, Clone, PartialEq where appropriate",
            "Use `thiserror` for library error types, `anyhow` for applications",
            "Document public APIs with `///` doc comments including examples",
            "Use `clippy` lints at warn level",
        ],
        anti_patterns=[
            "Do NOT use `.unwrap()` in production code",
            "Do NOT use `unsafe` without a safety comment",
            "Do NOT clone when a reference will do",
            "Do NOT use `String` when `&str` is sufficient",
            "Do NOT suppress clippy warnings without justification",
        ],
        common_commands={
            "build": "cargo build",
            "test": "cargo test",
            "lint": "cargo clippy -- -W warnings",
            "format": "cargo fmt",
            "doc": "cargo doc --open",
        },
    ),

    "nextjs": FrameworkPreset(...),
    "django": FrameworkPreset(...),
    "python-cli": FrameworkPreset(...),
    "go": FrameworkPreset(...),
    "node-express": FrameworkPreset(...),
}
```

### 3. Preset Packs (`src/anchormd/templates/presets.py`)

Curated preset combinations for common project types:

```python
PRESET_PACKS: dict[str, PresetPack] = {
    "default": PresetPack(
        name="Default",
        description="Auto-detect framework and apply matching preset",
        auto_detect=True,
    ),
    "monorepo": PresetPack(
        name="Monorepo",
        description="Multi-package repository with shared conventions",
        extra_sections=["Workspace Structure", "Package Dependencies"],
    ),
    "library": PresetPack(
        name="Library/Package",
        description="Published library with API docs focus",
        extra_sections=["Public API", "Versioning Policy", "Release Process"],
    ),
    "minimal": PresetPack(
        name="Minimal",
        description="Bare essentials only — overview, commands, anti-patterns",
        sections=["header", "current_state", "commands", "anti_patterns"],
    ),
}
```

### 4. Template Pydantic Models (add to `models.py`)

```python
class FrameworkPreset(BaseModel):
    name: str
    description: str
    coding_standards: list[str]
    anti_patterns: list[str]
    common_commands: dict[str, str]
    extra_sections: dict[str, str] = {}  # section_name -> template

class PresetPack(BaseModel):
    name: str
    description: str
    auto_detect: bool = False
    sections: list[str] | None = None  # None = all sections
    extra_sections: list[str] = []
```

### 5. Tests (`tests/test_templates.py`)

- Test: Each framework preset renders valid markdown
- Test: Auto-detect selects correct preset for Python/FastAPI project
- Test: Auto-detect selects correct preset for React/TS project
- Test: "minimal" pack produces fewer sections than "default"
- Test: Framework anti-patterns are included in generated output
- Test: Custom commands from preset appear in output
- Test: Unknown framework falls back to "default" gracefully
- Test: All preset rendering is deterministic (same input → same output)

## Acceptance Criteria
- `pytest tests/test_templates.py -v` — all pass
- At least 8 framework presets defined and rendering correctly
- `anchormd presets` lists all available presets
- `anchormd generate . --preset python-fastapi` uses that preset's defaults
- Auto-detection correctly identifies framework from project files
- `ruff check src/anchormd/templates/` — clean
