# CLAUDE.md — claudemd-forge

## Project Overview

claudemd-forge — Generate and audit CLAUDE.md files for AI coding agents. Scans codebases to detect languages, frameworks, and conventions, then produces production-grade configuration files for Claude Code, Cursor, Windsurf, and Codex.

## Current State

- **Version**: 0.1.0
- **Language**: Python
- **Files**: 46 across 1 languages
- **Lines**: 5,698

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
├── {src/
│   └── claudemd_forge/
├── .gitignore
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
- **Line Length**: 100 characters (configured in pyproject.toml)
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

### Dev
- pytest
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
- Audit Scoring

Forge
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
- `values`

## Git Conventions

- Commit messages: Conventional commits  (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- Branch naming: `feat/description`, `fix/description`
- Run tests before committing
