# CLAUDE.md — RedOPS

## Project Overview

Advanced modular AI-assisted recon, forensics, and exposure-analysis framework

## Current State

- **Version**: 1.5.0
- **Language**: Python
- **Files**: 379 across 4 languages
- **Lines**: 172,126

## Architecture

```
RedOPS/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   └── workflows/
├── AreteDriver/
│   └── RedOPS/
├── assets/
├── completions/
├── config/
│   ├── pipelines/
│   └── systemd/
├── deploy/
│   ├── docker/
│   └── kubernetes/
├── docs/
│   ├── _static/
│   └── api/
├── examples/
│   ├── plugins/
│   └── sample_output/
├── man/
├── scripts/
├── src/
│   └── redops/
├── tests/
├── .dockerignore
├── .gitignore
├── CHANGELOG.md
├── CONTRIBUTING.md
├── Dockerfile
├── LICENSE
├── README.md
├── SETUP.md
├── alembic.ini
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
├── setup.py
```

## Tech Stack

- **Language**: Python, Shell, SQL, CSS
- **Framework**: fastapi
- **Package Manager**: pip
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
- **Line Length (p95)**: 70 characters

## Common Commands

```bash
# test
pytest tests/ -v
# coverage
pytest --cov=src/ tests/
# redops
redops.main:main
# redops-web
redops.web.app:main
# redops-mcp
redops.mcp.server:main

# docker ENTRYPOINT
["python", "-m", "redops.main"]
# docker CMD
["--help"]
```

## Anti-Patterns (Do NOT Do)

- Do NOT commit secrets, API keys, or credentials
- Do NOT skip writing tests for new code
- Do NOT hardcode secrets in Dockerfiles — use environment variables
- Do NOT use `latest` tag — pin specific versions
- Do NOT use synchronous database calls in async endpoints
- Do NOT return raw dicts — use Pydantic response models
- Do NOT use `os.path` — use `pathlib.Path` everywhere
- Do NOT use bare `except:` — catch specific exceptions
- Do NOT use mutable default arguments
- Do NOT use `print()` for logging — use the `logging` module

## Dependencies

### Core
- pydantic

### Dev
- pytest
- pytest-cov
- pytest-asyncio
- ruff
- mypy

## Domain Context

### Key Models/Classes
- `AIAssistant`
- `AIConfig`
- `AIRequest`
- `AIResponse`
- `APIError`
- `APIKey`
- `APIKeyCreate`
- `APIKeyRateLimiter`
- `APIKeyResponse`
- `APIKeyTenantResolver`
- `APIKeyWithSecret`
- `APIKeysConfig`
- `APIRequest`
- `APIResponse`
- `APIServer`

### Domain Terms
- AI
- ATT
- Accelerate Assessments
- Add Tests
- Artifact Detection
- Asset Graphing
- Asset Mapping
- Attack Path Inference
- Attack Path Modeling
- Attack Simulation

### API Endpoints
- `/`
- `/api/ai`
- `/api/auth/generate-api-key`
- `/api/auth/login`
- `/api/auth/logout`
- `/api/auth/status`
- `/api/data`
- `/api/health`
- `/api/protected`
- `/api/scans`
- `/api/scans/{scan_id}`
- `/api/scans/{scan_id}/results`
- `/api/settings/presets`
- `/api/settings/providers`
- `/api/ws/stats`

### Enums/Constants
- `ABUSEIPDB_API`
- `ACCEPTED_RISK`
- `ACKNOWLEDGED`
- `ACTIVE`
- `ADMIN`
- `AES_256_CBC`
- `AES_256_GCM`
- `AFTER_MODULE`
- `AFTER_PIPELINE`
- `AFTER_REPORT`

## Git Conventions

- Commit messages: Conventional commits  (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- Branch naming: `feat/description`, `fix/description`
- Run tests before committing
