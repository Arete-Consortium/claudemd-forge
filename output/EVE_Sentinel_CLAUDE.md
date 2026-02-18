# CLAUDE.md — EVE_Sentinel

## Project Overview

Alliance Intel & Recruitment Analysis Tool for EVE Online

## Current State

- **Version**: 0.1.0
- **Language**: Python
- **Files**: 147 across 5 languages
- **Lines**: 32,131

## Architecture

```
EVE_Sentinel/
├── .github/
│   └── workflows/
├── backend/
│   ├── analyzers/
│   ├── api/
│   ├── auth/
│   ├── connectors/
│   ├── data/
│   ├── database/
│   ├── discord_bot/
│   ├── ml/
│   ├── models/
│   ├── services/
│   └── ... (1 more)
├── docs/
├── frontend/
│   ├── static/
│   └── templates/
├── src-tauri/
│   └── src/
├── tests/
├── .dockerignore
├── .env.example
├── .gitignore
├── Dockerfile
├── LICENSE
├── Procfile
├── README.md
├── docker-compose.yml
├── fly.toml
├── pyproject.toml
├── railway.toml
├── render.yaml
├── run_bot.py
```

## Tech Stack

- **Language**: Python, HTML, CSS, Rust, JavaScript
- **Framework**: fastapi
- **Package Manager**: pip
- **Linters**: ruff
- **Formatters**: ruff
- **Type Checkers**: mypy
- **Test Frameworks**: pytest
- **Runtime**: Docker
- **CI/CD**: GitHub Actions

## Coding Standards

- **Naming**: snake_case
- **Quote Style**: double quotes
- **Type Hints**: present
- **Docstrings**: google style
- **Imports**: absolute
- **Path Handling**: mixed
- **Line Length (p95)**: 77 characters

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

# docker CMD
["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]
```

## Anti-Patterns (Do NOT Do)

- Do NOT commit secrets, API keys, or credentials
- Do NOT skip writing tests for new code
- Do NOT hardcode secrets in Dockerfiles — use environment variables
- Do NOT use `latest` tag — pin specific versions
- Do NOT use `os.path` — use `pathlib.Path` everywhere
- Do NOT use bare `except:` — catch specific exceptions
- Do NOT use mutable default arguments
- Do NOT use `print()` for logging — use the `logging` module
- Do NOT use synchronous database calls in async endpoints
- Do NOT return raw dicts — use Pydantic response models
- Do NOT use `.unwrap()` in production code — use proper error handling
- Do NOT use `unsafe` without a safety comment
- Do NOT clone when a reference will do

## Dependencies

### Core
- fastapi
- uvicorn

### Dev
- pytest
- pytest-asyncio
- pytest-cov
- mypy
- ruff
- httpx
- respx

## Domain Context

### Key Models/Classes
- `APIKeyInfo`
- `ActivityAnalyzer`
- `ActivityPattern`
- `AddToWatchlistRequest`
- `AllianceAuthAdapter`
- `AnalysisCog`
- `AnalysisReport`
- `AnalyticsDashboard`
- `Annotation`
- `AnnotationRecord`
- `AnnotationRepository`
- `Applicant`
- `AssetSummary`
- `AssetsAnalyzer`
- `AssetsSummary`

### Domain Terms
- AAB
- APK
- ARM
- AWOX
- Alliance Auth
- Alliance Auth Bridge
- Alliance Intel
- Alt Detection
- Android Play Store
- Android Studio

### API Endpoints
- `/`
- `/actions`
- `/admin`
- `/admin/rules`
- `/analytics`
- `/analyze`
- `/analyze-corp`
- `/analyze-fleet`
- `/analyze-me`
- `/analyze/batch`
- `/analyze/by-name/{character_name}`
- `/analyze/{character_id}`
- `/auth-status`
- `/batch`
- `/bulk-pdf`

### Enums/Constants
- `ACTIVE_PVPER`
- `ACTIVITY`
- `ADMIN`
- `ALLIED_NEGATIVE_STANDINGS`
- `ALLIED_STANDINGS`
- `ALTS`
- `API_MANIPULATION`
- `ASSETS`
- `AWOX_HISTORY`
- `BASE_URL`

### Outstanding Items
- **NOTE**: Static routes must be defined before dynamic routes to avoid path conflicts (`backend/api/analyze.py`)
- **TODO**: Get added_by from session (`backend/api/bulk.py`)
- **TODO**: Get created_by from session (`backend/api/rules.py`)

## Git Conventions

- Commit messages: Conventional commits  (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- Branch naming: `feat/description`, `fix/description`
- Run tests before committing
