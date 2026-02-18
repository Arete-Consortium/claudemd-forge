# CLAUDE.md — G13_Linux

## Project Overview

Logitech G13 Linux driver with macro support, RGB control, and LCD display management

## Current State

- **Version**: 1.5.6
- **Language**: Python
- **Files**: 213 across 6 languages
- **Lines**: 44,624

## Architecture

```
G13_Linux/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   └── workflows/
├── assets/
├── configs/
│   ├── macros/
│   └── profiles/
├── data/
├── gui-web/
│   ├── backend/
│   ├── public/
│   └── src/
├── packaging/
│   └── appimage/
├── resources/
├── scripts/
├── src/
│   └── g13_linux/
├── systemd/
├── tests/
├── tools/
├── udev/
├── .gitignore
├── .pre-commit-config.yaml
├── BACKGROUND_IMAGE_SETUP.md
├── BUTTON_MAPPING_GUIDE.md
├── BUTTON_MAPPING_STATUS.md
├── CHANGELOG.md
├── CLAUDE.md
├── CONTRIBUTING.md
├── G13LogitechOPS_GITHUB_READY.md
├── INSTALLATION.md
├── LICENSE
├── MANIFEST.in
├── README.md
├── RECORDING_SCRIPT.md
├── TROUBLESHOOTING.md
├── WORKFLOW_DOCUMENTATION.md
├── button_monitor.py
├── capture_buttons.py
├── capture_hidapi.py
├── capture_thumb_buttons.py
├── create_g13_layout.py
├── debug_hid.py
├── find_g13_device.sh
├── find_input_device.sh
├── g13-linux-gui.sh
├── g13-linux-launcher.sh
├── g13-linux.desktop
├── g13-linux.png
├── g13-linux.svg
├── generate_g13_background.py
├── generate_polished_g13.py
├── install-desktop.sh
├── install.sh
├── publish.sh
├── pyproject.toml
├── requirements.txt
├── test_buttons_sudo.py
├── test_direct_read.py
├── test_lcd.py
├── test_lcd_chunks.py
├── test_lcd_raw.py
├── verify_buttons.py
```

## Tech Stack

- **Language**: Python, TypeScript, Shell, CSS, JavaScript, HTML
- **Package Manager**: pip
- **Linters**: ruff
- **Formatters**: ruff
- **Type Checkers**: mypy
- **Test Frameworks**: pytest
- **CI/CD**: GitHub Actions

## Coding Standards

- **Naming**: snake_case
- **Quote Style**: double quotes
- **Type Hints**: partial
- **Docstrings**: google style
- **Imports**: mixed
- **Path Handling**: os.path
- **Line Length (p95)**: 76 characters

## Common Commands

```bash
# test
pytest tests/ -v
# lint
ruff check src/ tests/
# format
ruff format src/ tests/
# type check
mypy src/
# coverage
pytest --cov=src/ tests/
# g13-linux
g13_linux.cli:main
# g13-linux-gui
g13_linux.gui.main:main
```

## Anti-Patterns (Do NOT Do)

- Do NOT commit secrets, API keys, or credentials
- Do NOT skip writing tests for new code
- Do NOT use `any` type — define proper type interfaces
- Do NOT use `var` — use `const` or `let`
- Do NOT use `os.path` — use `pathlib.Path` everywhere
- Do NOT use bare `except:` — catch specific exceptions
- Do NOT use mutable default arguments
- Do NOT use `print()` for logging — use the `logging` module

## Dependencies

### Core
- hidapi
- evdev
- pyusb
- PyQt6
- pynput
- Pillow
- aiohttp

### Dev
- pytest
- pytest-cov
- pytest-qt
- ruff
- mypy
- build
- twine
- bandit

## Domain Context

### Key Models/Classes
- `AppProfileConfig`
- `AppProfileRule`
- `AppProfileRulesManager`
- `AppProfilesWidget`
- `ApplicationController`
- `BlockPyQt6Finder`
- `BrightnessScreen`
- `ButtonMapperWidget`
- `CalibrationDialog`
- `Canvas`
- `ClickableImageLabel`
- `ClockScreen`
- `ClockSettingsScreen`
- `ColorPickerScreen`
- `ColorPickerWidget`

### Domain Terms
- Add Rule
- App Profiles
- Application Profiles
- Application Profiles Automatically
- Backlight Control
- CI
- Configuration File Rules
- EVE
- GUI
- Gaming Keyboard

### API Endpoints
- `/api/macros`
- `/api/macros/{macro_id}`
- `/api/profiles`
- `/api/profiles/{name}`
- `/api/profiles/{name}/activate`
- `/api/status`

### Enums/Constants
- `ALERT`
- `ANALOG`
- `API_BASE`
- `AS_FAST`
- `BOTH`
- `BUTTON_BD`
- `BUTTON_LEFT`
- `BUTTON_M1`
- `BUTTON_M2`
- `BUTTON_M3`

### Outstanding Items
- **NOTE**: These are on Byte 5, NOT Byte 6 as previously predicted! (`src/g13_linux/gui/models/event_decoder.py`)
- **NOTE**: Don't update last_state here - let get_button_changes do it (`src/g13_linux/gui/models/event_decoder.py`)

## Git Conventions

- Commit messages: Conventional commits  (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- Branch naming: `feat/description`, `fix/description`
- Run tests before committing
