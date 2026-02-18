# CLAUDE.md — vdc-display

## Project Overview

TV Dashboard for Vehicle Distribution Center shift progress. Designed for facility floor displays showing real-time labor hours and production stage status.

## Current State

- **Language**: Python
- **Files**: 13 across 1 languages
- **Lines**: 1,034

## Architecture

```
vdc-display/
├── .github/
│   └── workflows/
├── modules/
├── tests/
├── .gitignore
├── README.md
├── app.py
├── requirements.txt
```

## Tech Stack

- **Language**: Python
- **Package Manager**: pip
- **CI/CD**: GitHub Actions

## Coding Standards

- **Naming**: snake_case
- **Quote Style**: double quotes
- **Type Hints**: partial
- **Docstrings**: google style
- **Imports**: absolute
- **Path Handling**: pathlib
- **Line Length (p95)**: 69 characters

## Anti-Patterns (Do NOT Do)

- Do NOT commit secrets, API keys, or credentials
- Do NOT skip writing tests for new code
- Do NOT use `os.path` — use `pathlib.Path` everywhere
- Do NOT use bare `except:` — catch specific exceptions
- Do NOT use mutable default arguments
- Do NOT use `print()` for logging — use the `logging` module

## Domain Context

### Key Models/Classes
- `TestCalculateShiftWorkload`
- `TestDatabaseConnection`
- `TestGetCurrentShift`
- `TestGetDemoData`
- `TestGetDemoStages`
- `TestQueryHelpers`
- `based`

### Domain Terms
- Carryover Display
- DB
- Display Optimization Designed
- Environment Variables
- FQA
- Kiosk Mode
- MIT
- Main Streamlit
- PPO
- Quick Start

### Enums/Constants
- `TV_STYLES`

## Git Conventions

- Commit messages: Conventional commits  (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- Branch naming: `feat/description`, `fix/description`
- Run tests before committing
