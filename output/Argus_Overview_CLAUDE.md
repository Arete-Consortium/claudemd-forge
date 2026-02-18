# CLAUDE.md — Argus_Overview

## Project Overview

Professional multi-boxing tool for EVE Online (Linux & Windows)

## Current State

- **Version**: 3.0.6
- **Language**: Python
- **Files**: 151 across 2 languages
- **Lines**: 57,694

## Architecture

```
Argus_Overview/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   └── workflows/
├── assets/
├── benchmarks/
├── docs/
│   └── screenshots/
├── flatpak/
├── packaging/
├── src/
│   └── argus_overview/
├── tests/
├── windows/
├── .gitignore
├── Argus_Overview.spec
├── CHANGELOG.md
├── CLAUDE.md
├── CODE_REVIEW.md
├── CONTRIBUTING.md
├── DEV_NOTES.md
├── LICENSE
├── PACKAGE_INFO.md
├── QUICKSTART.md
├── README.md
├── RECORDING_SCRIPT.md
├── REVIEW_COMPLETE.txt
├── REVIEW_SUMMARY.md
├── SECURITY.md
├── WHATS_NEW.md
├── argus-overview.spec
├── build-appimage.sh
├── build-portable.sh
├── install.sh
├── pyproject.toml
├── requirements-windows.txt
├── requirements.txt
├── run.sh
├── uninstall.sh
```

## Tech Stack

- **Language**: Python, Shell
- **Package Manager**: pip
- **Linters**: ruff
- **Formatters**: black, ruff
- **Test Frameworks**: pytest
- **CI/CD**: GitHub Actions

## Coding Standards

- **Naming**: snake_case
- **Quote Style**: double quotes
- **Type Hints**: present
- **Docstrings**: google style
- **Imports**: absolute
- **Path Handling**: pathlib
- **Line Length (p95)**: 74 characters

## Common Commands

```bash
# test
pytest tests/ -v
# lint
ruff check src/ tests/
# format
ruff format src/ tests/
# isort
isort src/ tests/
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
- Pillow
- pynput
- numpy
- watchdog

### Dev
- ruff
- isort
- pytest
- pytest-cov
- bandit

## Domain Context

### Key Models/Classes
- `AboutDialog`
- `ActionRegistry`
- `ActionScope`
- `ActionSpec`
- `AdvancedPanel`
- `AlertConfig`
- `AlertDispatcher`
- `AlertType`
- `AppearancePanel`
- `ArrangementGrid`
- `AutoDiscovery`
- `Character`
- `CharacterDialog`
- `CharacterManager`
- `CharacterTable`

### Domain Terms
- ALL
- ARCHITECTURE
- Account Trading
- Activity Indicators
- Arch Linux
- Argus Overview
- Auto Log Detection
- Bind Ctrl
- Boxing Solution
- Buy Me

### Enums/Constants
- `APP_MENU`
- `AUDIO`
- `CASCADE`
- `CHARACTER_CONTEXT`
- `CLEAR`
- `CRITICAL`
- `CUSTOM`
- `CYCLE_CONTROL_TOOLBAR`
- `DANGER`
- `DANGER_STYLE`

### Outstanding Items
- **NOTE**: MainWindowV21 is imported INSIDE main() AFTER single-instance check (`src/main.py`)

## Git Conventions

- Commit messages: Conventional commits  (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- Branch naming: `feat/description`, `fix/description`
- Run tests before committing
