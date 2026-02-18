# CLAUDE.md — RazerControls

## Project Overview

Razer Control Center for Linux - button remapping, macros, RGB lighting, and DPI control

## Current State

- **Version**: 1.9.8
- **Language**: Python
- **Files**: 182 across 2 languages
- **Lines**: 49,416

## Architecture

```
RazerControls/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   └── workflows/
├── apps/
│   ├── gui/
│   └── tray/
├── assets/
├── crates/
│   ├── device_layouts/
│   ├── device_registry/
│   ├── keycode_map/
│   ├── profile_schema/
│   └── zone_definitions/
├── data/
│   ├── device_images/
│   ├── device_layouts/
│   └── icons/
├── docs/
├── packaging/
│   ├── appimage/
│   ├── flatpak/
│   └── systemd/
├── razer-control-center_docs/
│   └── docs/
├── services/
│   ├── app_watcher/
│   ├── macro_engine/
│   ├── openrazer_bridge/
│   └── remap_daemon/
├── tests/
├── tools/
│   └── debug/
├── .gitignore
├── CHANGELOG.md
├── CLAUDE.md
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── LICENSE
├── MANIFEST.in
├── README.md
├── fix-permissions.sh
├── install.sh
├── publish.sh
├── pyproject.toml
```

## Tech Stack

- **Language**: Python, Shell
- **Package Manager**: pip
- **Linters**: ruff
- **Formatters**: black, ruff
- **Type Checkers**: mypy
- **Test Frameworks**: pytest
- **CI/CD**: GitHub Actions

## Coding Standards

- **Naming**: snake_case
- **Quote Style**: double quotes
- **Type Hints**: present
- **Docstrings**: google style
- **Imports**: absolute
- **Path Handling**: pathlib
- **Line Length (p95)**: 71 characters

## Common Commands

```bash
# test
pytest tests/ -v
# lint
ruff check src/ tests/
# format
black src/ tests/
# type check
mypy src/
# razer-control-center
apps.gui.main:main
# razer-tray
apps.tray.main:main
# razer-remap-daemon
services.remap_daemon.main:main
# razer-profile
tools.profile_cli:main
# razer-keymap
tools.keymap_check:main
# razer-device
tools.device_cli:main
# razer-macro
tools.macro_cli:main
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
- evdev
- pydbus
- pydantic
- pynput
- PyYAML
- PyGObject
- 
- # Pin to avoid girepository-2.0 requirement (needs Ubuntu 24.04+)

### Dev
- pytest
- pytest-cov
- pytest-asyncio
- ruff
- mypy

## Domain Context

### Key Models/Classes
- `ActionType`
- `ActiveBinding`
- `ActiveWindowInfo`
- `AddPatternDialog`
- `AnimatedWidget`
- `AppMatcherWidget`
- `AppSettings`
- `AppWatcher`
- `BatteryDeviceCard`
- `BatteryMonitorWidget`
- `Binding`
- `BindingDialog`
- `BindingEditorWidget`
- `ButtonBindingDialog`
- `ButtonShape`

### Domain Terms
- Add Binding
- Add Macro
- App Watcher
- Automatic Profile Switching
- Bindings Tab
- Button Remapping
- CI
- CTRL
- Configuration Profiles
- DPI

### Enums/Constants
- `ACTION_ADD`
- `ACTION_APPLY`
- `ACTION_DELETE`
- `ACTION_EDIT`
- `ACTION_EXPORT`
- `ACTION_IMPORT`
- `ACTION_PLAY`
- `ACTION_RECORD`
- `ACTION_REFRESH`
- `ACTION_SAVE`

## Git Conventions

- Commit messages: Conventional commits  (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- Branch naming: `feat/description`, `fix/description`
- Run tests before committing
