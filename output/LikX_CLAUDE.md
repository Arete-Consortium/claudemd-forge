# CLAUDE.md — LikX

## Project Overview

GTK3 screenshot tool for Linux with annotation, OCR, and cloud upload

## Current State

- **Version**: 3.30.0
- **Language**: Python
- **Files**: 194 across 3 languages
- **Lines**: 68,551

## Architecture

```
LikX/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   └── workflows/
├── AppDir/
│   ├── opt/
│   └── usr/
├── assets/
├── debian/
│   └── source/
├── docs/
│   └── images/
├── flatpak/
├── locale/
│   ├── de/
│   ├── es/
│   ├── fr/
│   ├── it/
│   ├── ja/
│   ├── pt/
│   └── ru/
├── resources/
│   └── icons/
├── scripts/
├── snap/
│   └── gui/
├── src/
│   ├── dialogs/
│   ├── mixins/
│   └── widgets/
├── tests/
├── .gitignore
├── .pre-commit-config.yaml
├── CHANGELOG.md
├── CLAUDE.md
├── CONTRIBUTING.md
├── LICENSE
├── README.md
├── build-appimage.sh
├── build-deb.sh
├── build-flatpak.sh
├── com.github.aretedriver.likx.yml
├── install-app.sh
├── likx.desktop
├── main.py
├── pyproject.toml
├── requirements.txt
├── setup.sh
```

## Tech Stack

- **Language**: Python, Shell, CSS
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
- **Imports**: mixed
- **Path Handling**: pathlib
- **Line Length (p95)**: 72 characters

## Common Commands

```bash
# test
pytest tests/ -v
# lint
ruff check src/ tests/
# format
ruff format src/ tests/
# coverage
pytest --cov=src/ tests/
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
- pycairo
- numpy
- 
- opencv-python-headless

### Dev
- pytest
- pytest-cov
- ruff

## Domain Context

### Key Models/Classes
- `ArrowStyle`
- `CaptureMode`
- `CaptureQueue`
- `CaptureResult`
- `Color`
- `Command`
- `CommandPalette`
- `DisplayServer`
- `DrawingElement`
- `DrawingMixin`
- `EditorState`
- `EditorWindow`
- `EditorWindowEnhancements`
- `GifRecorder`
- `HistoryEntry`

### Domain Terms
- Adding Translations
- CI
- Cloud Upload
- Color Picker
- Command Palette
- Editor Shortcuts
- From Source
- GIF
- GNOME
- GTK

### Enums/Constants
- `ACTIVE`
- `ARROW`
- `BLUR`
- `CALLOUT`
- `CAPTURING`
- `COLORPICKER`
- `COMPLETED`
- `CONFIG_KEY`
- `CROP`
- `DOMAIN`

## Git Conventions

- Commit messages: Conventional commits  (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- Branch naming: `feat/description`, `fix/description`
- Run tests before committing
