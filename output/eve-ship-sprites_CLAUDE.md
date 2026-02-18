# CLAUDE.md — eve-ship-sprites

## Project Overview

Top-down ship sprites rendered from EVE Online 3D models for use in 2D games.

## Current State

- **Language**: Python
- **Files**: 379 across 2 languages
- **Lines**: 3,253

## Architecture

```
eve-ship-sprites/
├── amarr/
│   ├── battlecruiser/
│   ├── battleship/
│   ├── capital/
│   ├── cruiser/
│   ├── destroyer/
│   ├── fighter/
│   ├── freighter/
│   ├── frigate/
│   └── industrial/
├── audit_sheets/
├── caldari/
│   ├── battlecruiser/
│   ├── battleship/
│   ├── capital/
│   ├── cruiser/
│   ├── destroyer/
│   ├── fighter/
│   ├── freighter/
│   ├── frigate/
│   └── industrial/
├── concord/
│   ├── battleship/
│   ├── cruiser/
│   └── frigate/
├── gallente/
│   ├── battlecruiser/
│   ├── battleship/
│   ├── capital/
│   ├── cruiser/
│   ├── destroyer/
│   ├── fighter/
│   ├── frigate/
│   └── industrial/
├── jove/
│   ├── battleship/
│   └── capsule/
├── minmatar/
│   ├── battlecruiser/
│   ├── battleship/
│   ├── capital/
│   ├── cruiser/
│   ├── destroyer/
│   ├── fighter/
│   ├── frigate/
│   └── industrial/
├── ore/
│   ├── barge/
│   ├── capital/
│   ├── command/
│   ├── exhumer/
│   └── frigate/
├── pirate/
│   ├── angel cartel/
│   ├── blood raiders/
│   ├── fighter/
│   ├── mordus legion/
│   ├── sanshas nation/
│   ├── soct/
│   └── soe/
├── rogue/
├── sheets/
├── sleeper/
├── special_edition/
├── triglavian/
├── upwell/
├── .gitignore
├── LICENSE
├── MANUAL_FIXES_NEEDED.md
├── README.md
├── copy_to_rebellion.py
├── generate_audit_sheet.py
├── generate_sprites.sh
├── generate_spritesheets.sh
├── prepare_for_rebellion.sh
├── render_ship.py
├── rerender_all_overrides.sh
├── rerender_all_scaled.sh
├── rerender_fixed.sh
├── rerender_for_game.sh
├── rerender_list.txt
├── rerender_problem_ships.sh
├── ship_orientations.json
├── ship_sizes.json
```

## Tech Stack

- **Language**: Python, Shell

## Coding Standards

- **Naming**: snake_case
- **Type Hints**: partial
- **Docstrings**: google style
- **Imports**: absolute
- **Path Handling**: os.path
- **Line Length (p95)**: 73 characters

## Anti-Patterns (Do NOT Do)

- Do NOT commit secrets, API keys, or credentials
- Do NOT skip writing tests for new code
- Do NOT use `os.path` — use `pathlib.Path` everywhere
- Do NOT use bare `except:` — catch specific exceptions
- Do NOT use mutable default arguments
- Do NOT use `print()` for logging — use the `logging` module

## Domain Context

### Key Models/Classes
- `default`
- `defaults`

### Domain Terms
- CCP
- Directory Structure
- EVE
- Explicit Euler
- Fill Ratio
- JSON
- License Ship
- Orientation System Ships
- Ship Sprites Top
- Size Scaling Ships

## Git Conventions

- Commit messages: Conventional commits  (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- Branch naming: `feat/description`, `fix/description`
- Run tests before committing
