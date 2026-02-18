# CLAUDE.md — flathub

## Project Overview

Flathub is the central place for building and hosting Flatpak builds.

## Current State

- **Language**: Python
- **Files**: 29 across 2 languages
- **Lines**: 1,830

## Architecture

```
flathub/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   ├── actions/
│   ├── images/
│   ├── scripts/
│   └── workflows/
├── CONTRIBUTING.md
├── COPYING
├── README.md
```

## Tech Stack

- **Language**: Python, Shell
- **CI/CD**: GitHub Actions

## Coding Standards

- **Naming**: snake_case
- **Quote Style**: double quotes
- **Type Hints**: present
- **Imports**: absolute
- **Path Handling**: mixed
- **Line Length (p95)**: 78 characters

## Anti-Patterns (Do NOT Do)

- Do NOT commit secrets, API keys, or credentials
- Do NOT skip writing tests for new code
- Do NOT use `os.path` — use `pathlib.Path` everywhere
- Do NOT use bare `except:` — catch specific exceptions
- Do NOT use mutable default arguments
- Do NOT use `print()` for logging — use the `logging` module

## Domain Context

### Domain Terms
- CONTRIBUTING
- Flathub Flathub

## Git Conventions

- Commit messages: Conventional commits  (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- Branch naming: `feat/description`, `fix/description`
- Run tests before committing
