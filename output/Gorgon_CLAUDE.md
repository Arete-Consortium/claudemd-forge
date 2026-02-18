# CLAUDE.md — Gorgon

## Project Overview

Multi-agent orchestration framework for production AI workflows

## Current State

- **Version**: 1.2.0
- **Language**: Python
- **Files**: 772 across 7 languages
- **Lines**: 248,790

## Architecture

```
Gorgon/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   └── workflows/
├── assets/
├── config/
├── deploy/
│   └── templates/
├── docs/
│   ├── adr/
│   └── integrations/
├── eval_suites/
├── examples/
│   └── 3d-assets/
├── frontend/
│   ├── public/
│   └── src/
├── migrations/
├── prompts/
├── scripts/
├── skills/
│   ├── browser/
│   ├── email/
│   ├── integrations/
│   └── system/
├── src/
│   └── test_ai/
├── tests/
│   ├── dashboard/
│   └── tui/
├── workflows/
│   └── examples/
├── .dockerignore
├── .env.example
├── .gitignore
├── .gitleaks.toml
├── .pre-commit-config.yaml
├── ARCHITECTURE.md
├── CHANGELOG.md
├── CLAUDE.md
├── CONTRIBUTING.md
├── Dockerfile
├── IMPLEMENTATION.md
├── LICENSE
├── QUICKSTART.md
├── README.md
├── docker-compose.yml
├── gorgon
├── gorgon-launcher.sh
├── gorgon.example.yaml
├── init.sh
├── poetry.lock
├── pyproject.toml
├── requirements.txt
├── run_api.sh
├── run_dashboard.sh
```

## Tech Stack

- **Language**: Python, TypeScript, SQL, Shell, JavaScript, HTML, CSS
- **Framework**: fastapi
- **Package Manager**: pip, poetry
- **Test Frameworks**: pytest
- **Runtime**: Docker
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
# coverage
pytest --cov=src/ tests/
# gorgon
test_ai.cli:app

# docker CMD
["uvicorn", "test_ai.api:app", "--host", "0.0.0.0", "--port", "8000"]
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
- Do NOT use `any` type — define proper type interfaces
- Do NOT use `var` — use `const` or `let`
- Do NOT hardcode secrets in Dockerfiles — use environment variables
- Do NOT use `latest` tag — pin specific versions

## Dependencies

### Core
- openai
- anthropic
- fastapi
- uvicorn
- streamlit
- google-auth
- google-auth-oauthlib
- google-auth-httplib2
- google-api-python-client
- notion-client
- PyGithub
- pydantic
- pydantic-settings
- python-dotenv
- aiofiles

### Dev
- pytest
- pytest-cov
- pytest-asyncio

## Domain Context

### Key Models/Classes
- `AIHandlersMixin`
- `APIClientMetricsCollector`
- `APIError`
- `APIException`
- `APIKeyCreate`
- `APIKeyCreateRequest`
- `APIKeyInfo`
- `APIKeyStatus`
- `ActionType`
- `AdaptiveAllocation`
- `AdaptiveRateLimitConfig`
- `AdaptiveRateLimitState`
- `AgentContext`
- `AgentContract`
- `AgentDefinitionResponse`

### Domain Terms
- AI
- Application Layer Auth
- Audit Logging
- CI
- CORS
- Client Layer Streamlit
- Contracts Checkpoints Resilience
- DAG
- Data Engineer
- Gorgon Production

### API Endpoints
- `/`
- `/agents`
- `/agents/{agent_id}`
- `/auth/login`
- `/budgets`
- `/budgets/summary`
- `/budgets/{budget_id}`
- `/budgets/{budget_id}/add-usage`
- `/budgets/{budget_id}/reset`
- `/credentials`
- `/credentials/{credential_id}`
- `/dashboard/budget`
- `/dashboard/recent-executions`
- `/dashboard/stats`
- `/dashboard/usage/by-agent`

### Enums/Constants
- `ABSTAIN`
- `ACKNOWLEDGED`
- `ACTIVE`
- `ADMIN`
- `AI_PROVIDER`
- `ALERT`
- `ALLOW`
- `ANALYST`
- `ANALYTICS`
- `ANALYZE`

### Outstanding Items
- **TODO**: Implement actual cancellation via API (`frontend/src/stores/chatStore.ts`)
- **TODO**: fix this bug\n") (`tests/test_self_improve_coverage.py`)

## Git Conventions

- Commit messages: Conventional commits  (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- Branch naming: `feat/description`, `fix/description`
- Run tests before committing
