# CLAUDE.md — claudemd-forge

## Project Overview

Generate and audit CLAUDE.md files for AI coding agents

## Current State

- **Version**: 0.2.0
- **Language**: Python
- **Files**: 130 across 3 languages
- **Lines**: 15,518

## Architecture

```
claudemd-forge/
├── .github/
│   └── workflows/
├── docs/
├── license_server/
│   ├── migrations/
│   └── routes/
├── output/
├── packs/
│   ├── django-pro/
│   ├── fastapi-pro/
│   ├── nextjs-pro/
│   └── rust-pro/
├── prompts/
├── scripts/
├── src/
│   └── claudemd_forge/
├── tests/
│   └── license_server/
├── .gitignore
├── .gitleaks.toml
├── BUILD_GUIDE.md
├── CLAUDE.md
├── LICENSE
├── README.md
├── action.yml
├── pyproject.toml
```

## Tech Stack

- **Language**: Python, HTML, SQL
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
- **Line Length (p95)**: 77 characters
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
- httpx

## Domain Context

### Key Models/Classes
- `AccuracyChecker`
- `ActivateRequest`
- `ActivateResponse`
- `AnalysisError`
- `AnalysisResult`
- `AntiPatternChecker`
- `AuditFinding`
- `AuditReport`
- `BaseTemplate`
- `ClaudeMdAuditor`
- `CodebaseScanner`
- `CommandAnalyzer`
- `CoverageChecker`
- `DocumentComposer`
- `DomainAnalyzer`

### Domain Terms
- AI
- Action Add
- Activate Pro
- App Router
- Audit Scoring Forge
- CD
- CI
- CLAUDE
- CMDF
- Claude Code

### API Endpoints
- `/users`
- `/users/{id}`
- `/v1/activate`
- `/v1/health`
- `/v1/validate`

### Enums/Constants
- `FREE`
- `PRO`
- `_ENV_LICENSE_KEY`
- `_ENV_LICENSE_SERVER`
- `_KEY_SALT`
- `_VALID_KEY`
- `import`
- `values`

## Git Conventions

- Commit messages: Conventional commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- Branch naming: `feat/description`, `fix/description`
- Run tests before committing
