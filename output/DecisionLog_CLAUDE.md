# CLAUDE.md — DecisionLog

## Project Overview

Automatic documentation system that tracks high-leverage decisions across projects.

## Current State

- **Language**: Python
- **Files**: 7 across 1 languages
- **Lines**: 949

## Architecture

```
DecisionLog/
├── .gitignore
├── DECISIONS.md
├── LICENSE
├── PROMPTS.md
├── README.md
├── arete-decision-log_claude-code.md
├── scan-decisions.py
```

## Tech Stack

- **Language**: Python

## Coding Standards

- **Naming**: snake_case
- **Quote Style**: double quotes
- **Type Hints**: present
- **Imports**: absolute
- **Path Handling**: pathlib
- **Line Length (p95)**: 86 characters

## Anti-Patterns (Do NOT Do)

- Do NOT commit secrets, API keys, or credentials
- Do NOT skip writing tests for new code
- Do NOT use `os.path` — use `pathlib.Path` everywhere
- Do NOT use bare `except:` — catch specific exceptions
- Do NOT use mutable default arguments
- Do NOT use `print()` for logging — use the `logging` module

## Domain Context

### Key Models/Classes
- `based`

### Domain Terms
- ADL
- ARCH
- Arete Decision Log
- Chosen Option
- Claude Code
- Claude Code Skill The
- DECISIONS
- Decision Class
- Decision Classes
- Entry Format

## Git Conventions

- Commit messages: Conventional commits  (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- Branch naming: `feat/description`, `fix/description`
- Run tests before committing
