# CLAUDE.md — vdc-core

## Project Overview

Domain models, protocols, and pure calculations for VDC operations

## Current State

- **Version**: 0.1.0
- **Language**: Python
- **Files**: 17 across 1 languages
- **Lines**: 978

## Architecture

```
vdc-core/
├── tests/
├── vdc_core/
│   ├── adapters/
│   ├── calculations/
│   └── protocols/
├── .gitignore
├── README.md
├── pyproject.toml
```

## Tech Stack

- **Language**: Python
- **Package Manager**: pip
- **Linters**: ruff
- **Formatters**: ruff
- **Test Frameworks**: pytest

## Coding Standards

- **Naming**: snake_case
- **Quote Style**: double quotes
- **Type Hints**: present
- **Imports**: absolute
- **Path Handling**: mixed
- **Line Length (p95)**: 76 characters

## Common Commands

```bash
# test
pytest tests/ -v
# lint
ruff check src/ tests/
# format
ruff format src/ tests/
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
- `Carryover`
- `LaborHours`
- `Shift`
- `ShiftRepository`
- `ShiftType`
- `SqliteShiftRepository`
- `SqliteStageRepository`
- `Stage`
- `StageBreakdown`
- `StageRepository`
- `TestCarryoverHours`
- `TestEfficiency`
- `TestLaborHours`
- `TestPercentComplete`
- `TestProtocolConformance`

### Domain Terms
- Adapters Concrete
- DAY
- Domain Models
- IO
- Protocols Structural
- Pure Calculations No
- Vehicle Distribution Center

### Enums/Constants
- `ARRIVED`
- `DAY`
- `DELIVERED`
- `IN_PRODUCTION`
- `NIGHT`
- `PENDING_DELIVERY`
- `SCHEMA`
- `import`

## Git Conventions

- Commit messages: Conventional commits  (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- Branch naming: `feat/description`, `fix/description`
- Run tests before committing
