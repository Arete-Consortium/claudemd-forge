# CLAUDE.md — EVE_Ships

## Project Overview

**267 vector ship silhouettes from the EVE Online universe.**

## Current State

- **Language**: Python
- **Files**: 271 across 1 languages
- **Lines**: 26,041

## Architecture

```
EVE_Ships/
├── audit_sheets/
├── ships/
├── .gitignore
├── LICENSE
├── README.md
├── generate_svg_audit.py
```

## Tech Stack

- **Language**: Python

## Coding Standards

- **Naming**: snake_case
- **Type Hints**: present
- **Imports**: absolute
- **Path Handling**: pathlib
- **Line Length (p95)**: 65 characters

## Anti-Patterns (Do NOT Do)

- Do NOT commit secrets, API keys, or credentials
- Do NOT skip writing tests for new code
- Do NOT use `os.path` — use `pathlib.Path` everywhere
- Do NOT use bare `except:` — catch specific exceptions
- Do NOT use mutable default arguments
- Do NOT use `print()` for logging — use the `logging` module

## Domain Context

### Domain Terms
- Adding Ships
- Build Integration
- Buy Me
- By Class
- By Faction
- CCP
- CSS
- Clone Everything
- Complete Ship List
- DOCTYPE

## Git Conventions

- Commit messages: Conventional commits  (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- Branch naming: `feat/description`, `fix/description`
- Run tests before committing
