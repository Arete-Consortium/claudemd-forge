# CLAUDE.md — Dossier

## Project Overview

Local-first document intelligence system

## Current State

- **Version**: 0.3.0
- **Language**: Python
- **Files**: 46 across 2 languages
- **Lines**: 12,581

## Architecture

```
Dossier/
├── .github/
│   └── workflows/
├── docs/
├── dossier/
│   ├── api/
│   ├── core/
│   ├── db/
│   ├── forensics/
│   ├── ingestion/
│   └── static/
├── tests/
├── .gitignore
├── README.md
├── pyproject.toml
├── requirements.txt
```

## Tech Stack

- **Language**: Python, HTML
- **Framework**: fastapi
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
- **Imports**: absolute
- **Path Handling**: pathlib
- **Line Length (p95)**: 79 characters

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
- Do NOT use synchronous database calls in async endpoints
- Do NOT return raw dicts — use Pydantic response models

## Dependencies

### Core
- fastapi
- uvicorn

### Dev
- pytest
- pytest-cov
- pytest-benchmark
- httpx
- ruff

## Domain Context

### Key Models/Classes
- `CandidateMatch`
- `Community`
- `DatePrecision`
- `EntityResolver`
- `ExtractedDate`
- `GraphAnalyzer`
- `GraphStats`
- `MergeAction`
- `NodeMetrics`
- `PathResult`
- `ResolutionResult`
- `TestAliases`
- `TestBelowThreshold`
- `TestBuildGraph`
- `TestBulkInsertBenchmark`

### Domain Terms
- Court Records
- Customizing Categories Edit
- DOSSIER
- Document Intelligence System
- Endpoints Once
- FOIA
- GET
- HTML
- MIT
- NER

### API Endpoints
- `/`
- `/aliases/{entity_id}`
- `/api/connections`
- `/api/documents`
- `/api/documents/{doc_id}`
- `/api/documents/{doc_id}/flag`
- `/api/entities`
- `/api/entities/{entity_id}/documents`
- `/api/ingest-directory`
- `/api/ingest-emails-directory`
- `/api/keywords`
- `/api/lobbying/generate`
- `/api/search`
- `/api/stats`
- `/api/upload`

### Enums/Constants
- `APPROXIMATE`
- `AUTO_MERGE`
- `BASE_URL`
- `DAY`
- `FARA_SEARCH_URL`
- `LDA_BASE_URL`
- `MONTH`
- `NO_MERGE`
- `RELATIVE`
- `RESOLVER_SCHEMA`

## Git Conventions

- Commit messages: Conventional commits  (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- Branch naming: `feat/description`, `fix/description`
- Run tests before committing
