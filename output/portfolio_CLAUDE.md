# CLAUDE.md — portfolio

## Project Overview

---

## Current State

- **Language**: Python
- **Files**: 5 across 1 languages
- **Lines**: 403

## Architecture

```
portfolio/
├── claude_notes/
├── scripts/
├── .gitignore
├── LICENSE
├── README.md
```

## Tech Stack

- **Language**: Python

## Coding Standards

- **Naming**: snake_case
- **Quote Style**: double quotes
- **Type Hints**: present
- **Imports**: absolute
- **Path Handling**: pathlib
- **Line Length (p95)**: 71 characters

## Anti-Patterns (Do NOT Do)

- Do NOT commit secrets, API keys, or credentials
- Do NOT skip writing tests for new code
- Do NOT use `os.path` — use `pathlib.Path` everywhere
- Do NOT use bare `except:` — catch specific exceptions
- Do NOT use mutable default arguments
- Do NOT use `print()` for logging — use the `logging` module

## Domain Context

### Domain Terms
- ABOUT
- AI
- ARETE
- Arcade Shooter Top
- Argus Overview
- Automation Engineer
- BRING
- Buy Me
- CD
- CI

### Enums/Constants
- `CLAUDE_MODEL`

## Git Conventions

- Commit messages: Conventional commits  (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- Branch naming: `feat/description`, `fix/description`
- Run tests before committing
