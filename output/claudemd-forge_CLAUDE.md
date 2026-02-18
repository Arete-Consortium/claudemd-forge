# CLAUDE.md — claudemd-forge

## Project Overview

Generate and audit CLAUDE.md files for AI coding agents

## Current State

- **Version**: 0.1.0
- **Language**: Python
- **Files**: 54 across 1 languages
- **Lines**: 7,627

## Architecture

```
claudemd-forge/
├── .github/
│   └── workflows/
├── docs/
├── prompts/
├── src/
│   └── claudemd_forge/
├── tests/
├── .gitignore
├── .gitleaks.toml
├── BUILD_GUIDE.md
├── CLAUDE.md
├── LICENSE
├── README.md
├── pyproject.toml
```

## Tech Stack

- **Language**: Python
- **Package Manager**: pip
- **Linters**: ruff
- **Formatters**: ruff
- **Type Checkers**: mypy
- **Test Frameworks**: pytest
- **CI/CD**: GitHub Actions

## Coding Standards

- **Naming**: snake_case
- **Quote Style**: double quotes
- **Type Hints**: present
- **Imports**: absolute
- **Path Handling**: pathlib
- **Line Length (p95)**: 78 characters
- **Error Handling**: Custom exception classes present

## Common Commands

```bash
# test
pytest tests/ -v
# lint
ruff check src/ tests/
# format
ruff format src/ tests/
# type check
mypy src/
# claudemd-forge
claudemd_forge.cli:app
```

## Anti-Patterns (Do NOT Do)

- Do NOT commit secrets, API keys, or credentials
- Do NOT skip writing tests for new code
- Do NOT use `os.path` — use `pathlib.Path` everywhere
- Do NOT use bare `except:` — catch specific exceptions
- Do NOT use mutable default arguments
- Do NOT use `print()` for logging — use the `logging` module

## Dependencies

### Core
- typer
- rich
- pydantic
- tomli
- pyyaml
- jinja2

### Dev
- pytest
- mypy
- ruff

## Domain Context

### Key Models/Classes
- `AnalysisError`
- `AnalysisResult`
- `AuditFinding`
- `AuditReport`
- `BaseTemplate`
- `ClaudeMdAuditor`
- `CodebaseScanner`
- `CommandAnalyzer`
- `DocumentComposer`
- `DomainAnalyzer`
- `FileInfo`
- `ForgeConfig`
- `ForgeError`
- `FrameworkPreset`
- `LanguageAnalyzer`

### Domain Terms
- AI
- App Router
- Audit Scoring Forge
- CD
- CI
- CLAUDE
- Claude Code
- Coding Standards
- Common Commands
- Current State

### API Endpoints
- `/users`
- `/users/{id}`

### Enums/Constants
- `FREE`
- `PRO`
- `_ENV_LICENSE_KEY`
- `_KEY_SALT`
- `import`
- `values`

## Git Conventions

- Commit messages: Conventional commits  (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- Branch naming: `feat/description`, `fix/description`
- Run tests before committing
