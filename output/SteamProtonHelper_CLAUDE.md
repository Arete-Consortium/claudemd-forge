# CLAUDE.md — SteamProtonHelper

## Project Overview

A comprehensive Linux tool to help setup Steam and Proton for gaming

## Current State

- **Version**: 2.3.3
- **Language**: Python
- **Files**: 43 across 2 languages
- **Lines**: 16,744

## Architecture

```
SteamProtonHelper/
├── .github/
│   └── workflows/
├── assets/
├── completions/
├── gui/
│   ├── widgets/
│   └── workers/
├── resources/
├── .gitignore
├── CHANGELOG.md
├── CLAUDE.md
├── CONTRIBUTING.md
├── DEPLOYMENT_READINESS.md
├── EXAMPLES.md
├── LICENSE
├── MAINTAINER_GUIDE.md
├── MANIFEST.in
├── README.md
├── install.sh
├── pyproject.toml
├── requirements-gui.txt
├── requirements.txt
├── setup.py
├── steam-proton-helper.desktop
├── steam_proton_helper.py
├── steam_proton_helper_gui.py
├── test_steam_proton_helper.py
├── uninstall.sh
```

## Tech Stack

- **Language**: Python, Shell
- **Package Manager**: pip
- **Test Frameworks**: pytest
- **CI/CD**: GitHub Actions

## Coding Standards

- **Naming**: snake_case
- **Quote Style**: double quotes
- **Type Hints**: partial
- **Docstrings**: google style
- **Imports**: absolute
- **Path Handling**: os.path
- **Line Length (p95)**: 81 characters
- **Error Handling**: Custom exception classes present

## Common Commands

```bash
# test
pytest tests/ -v
# steam-proton-helper
steam_proton_helper:main
# steam-proton-helper-gui
steam_proton_helper_gui:main
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
- pytest-timeout

## Domain Context

### Key Models/Classes
- `CheckStatus`
- `CheckWorker`
- `ChecksPanel`
- `Color`
- `CompatdataInfo`
- `DependencyCheck`
- `DependencyChecker`
- `DistroDetector`
- `FixDialog`
- `GEProtonRelease`
- `GameLaunchProfile`
- `GameSearchWorker`
- `InstalledGame`
- `LogEntry`
- `MainWindow`

### Domain Terms
- ACF
- ACO
- ACTION
- AMD
- ANSI
- Advanced Features
- Arch Linux
- Automated Detection
- Basic Usage
- Best Reported

### Enums/Constants
- `BLUE`
- `BOLD`
- `CYAN`
- `DIM`
- `END`
- `FAIL`
- `FLATPAK`
- `GREEN`
- `NATIVE`
- `NONE`

## Git Conventions

- Commit messages: Conventional commits  (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- Branch naming: `feat/description`, `fix/description`
- Run tests before committing
