# CLAUDE.md — animus

## Project Overview

An exocortex architecture for personal cognitive sovereignty

## Current State

- **Version**: 0.6.0
- **Language**: Python
- **Files**: 66 across 1 languages
- **Lines**: 21,981

## Architecture

```
animus/
├── .github/
│   └── workflows/
├── animus/
│   ├── integrations/
│   ├── learning/
│   ├── protocols/
│   └── sync/
├── docs/
├── examples/
├── tests/
├── .gitignore
├── CONTRIBUTING.md
├── LICENSE
├── README.md
├── pyproject.toml
```

## Tech Stack

- **Language**: Python
- **Framework**: fastapi
- **Package Manager**: pip
- **Linters**: ruff
- **Formatters**: ruff
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
# coverage
pytest --cov=src/ tests/
# animus
animus.__main__:main
```

## Anti-Patterns (Do NOT Do)

- Do NOT commit secrets, API keys, or credentials
- Do NOT skip writing tests for new code
- Do NOT use `os.path` — use `pathlib.Path` everywhere
- Do NOT use bare `except:` — catch specific exceptions
- Do NOT use mutable default arguments
- Do NOT use `print()` for logging — use the `logging` module
- Do NOT use synchronous database calls in async endpoints
- Do NOT return raw dicts — use Pydantic response models

## Dependencies

### Core
- ollama
- chromadb
- pyyaml
- pydantic
- rich
- prompt-toolkit

### Dev
- pytest
- pytest-cov
- ruff
- mypy
- pre-commit
- httpx

## Domain Context

### Key Models/Classes
- `APIConfig`
- `APIServer`
- `AnimusConfig`
- `AnthropicModel`
- `AppState`
- `ApprovalManager`
- `ApprovalRequest`
- `ApprovalRequirement`
- `ApprovalStatus`
- `AuthType`
- `BaseIntegration`
- `BriefResponse`
- `ChatRequest`
- `ChatResponse`
- `ChromaMemoryStore`

### Domain Terms
- AI
- ANIMUS
- ARCHITECTURE
- Acknowledgments This
- Architecture Animus
- Architecture Overview
- Buildable Now
- CONVERGENT
- Cognitive Layer
- Cognitive Layer The

### API Endpoints
- `/brief`
- `/chat`
- `/decide`
- `/guardrails`
- `/integrations`
- `/integrations/{service}`
- `/integrations/{service}/connect`
- `/learning/history`
- `/learning/items`
- `/learning/rollback-points`
- `/learning/rollback/{point_id}`
- `/learning/scan`
- `/learning/status`
- `/learning/{item_id}`
- `/learning/{item_id}/approve`

### Enums/Constants
- `ACCESS`
- `ACTIVE`
- `ANTHROPIC`
- `API_KEY`
- `APPROVE`
- `APPROVED`
- `AUTH`
- `AUTH_FAIL`
- `AUTH_OK`
- `AUTO`

### Outstanding Items
- **TODO**: Encrypt credentials before saving (`animus/integrations/manager.py`)
- **TODO**: Use since_version for incremental sync (`animus/sync/server.py`)

## Git Conventions

- Commit messages: Conventional commits  (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- Branch naming: `feat/description`, `fix/description`
- Run tests before committing
