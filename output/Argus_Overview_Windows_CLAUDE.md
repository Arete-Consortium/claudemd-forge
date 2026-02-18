# CLAUDE.md — Argus_Overview_Windows

## Project Overview

Professional multi-boxing tool for EVE Online on Windows

## Current State

- **Version**: 2.5.0
- **Language**: Python
- **Files**: 56 across 1 languages
- **Lines**: 14,510

## Architecture

```
Argus_Overview_Windows/
├── .github/
│   └── workflows/
├── assets/
├── scripts/
├── src/
│   └── argus_overview/
├── tests/
├── .gitignore
├── Argus_Overview.spec
├── LICENSE
├── README.md
├── installer.iss
├── pyproject.toml
├── version_info.txt
```

## Tech Stack

- **Language**: Python
- **Package Manager**: pip
- **Linters**: ruff
- **Formatters**: ruff
- **Test Frameworks**: pytest
- **CI/CD**: GitHub Actions

## Coding Standards

- **Naming**: snake_case
- **Quote Style**: double quotes
- **Type Hints**: present
- **Docstrings**: google style
- **Imports**: absolute
- **Path Handling**: pathlib
- **Line Length (p95)**: 73 characters

## Common Commands

```bash
# test
pytest tests/ -v
# lint
ruff check src/ tests/
# format
ruff format src/ tests/
# argus-overview
main:main
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
- PySide6
- pywin32
- Pillow
- pynput
- numpy
- watchdog

### Dev
- ruff
- pytest
- pytest-cov

## Domain Context

### Key Models/Classes
- `AboutDialog`
- `ActionRegistry`
- `ActionScope`
- `ActionSpec`
- `AdvancedPanel`
- `AlertConfig`
- `AlertDetector`
- `AlertDispatcher`
- `AlertLevel`
- `AlertType`
- `AlertsPanel`
- `AppearancePanel`
- `ArrangementGrid`
- `AutoDiscovery`
- `Character`

### Domain Terms
- Alert Detection
- Argus Overview
- Build Windows
- Buy Me
- CI
- Character Management
- Configuration Settings
- Creates Start Menu
- Default Hotkeys
- Download Latest Release

### Enums/Constants
- `APP_MENU`
- `AUDIO`
- `AUTOMATION_TOOLBAR`
- `CASCADE`
- `CHARACTER_CONTEXT`
- `CLEAR`
- `CRITICAL`
- `CUSTOM`
- `DANGER`
- `DANGER_STYLE`

## Git Conventions

- Commit messages: Conventional commits  (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- Branch naming: `feat/description`, `fix/description`
- Run tests before committing
