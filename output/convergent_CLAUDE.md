# CLAUDE.md — convergent

## Project Overview

Multi-agent coherence and coordination for AI systems

## Current State

- **Version**: 1.0.0
- **Language**: Python
- **Files**: 75 across 2 languages
- **Lines**: 24,024

## Architecture

```
convergent/
├── .github/
│   └── workflows/
├── benches/
├── docs/
├── python/
│   └── convergent/
├── scripts/
├── src/
├── tests/
├── .gitignore
├── CHANGELOG.md
├── CLAUDE.md
├── Cargo.toml
├── LICENSE
├── README.md
├── pyproject.toml
```

## Tech Stack

- **Language**: Python, Rust
- **Framework**: rust
- **Package Manager**: pip
- **Linters**: clippy, ruff
- **Formatters**: ruff
- **Type Checkers**: mypy
- **Test Frameworks**: cargo test, pytest
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
```

## Anti-Patterns (Do NOT Do)

- Do NOT commit secrets, API keys, or credentials
- Do NOT skip writing tests for new code
- Do NOT use `os.path` — use `pathlib.Path` everywhere
- Do NOT use bare `except:` — catch specific exceptions
- Do NOT use mutable default arguments
- Do NOT use `print()` for logging — use the `logging` module
- Do NOT use `.unwrap()` in production code — use proper error handling
- Do NOT use `unsafe` without a safety comment
- Do NOT clone when a reference will do

## Dependencies

### Core
- pyo3
- rusqlite
- serde
- serde_json
- uuid
- chrono

### Dev
- pytest
- pytest-asyncio
- pytest-benchmark
- ruff
- mypy

## Domain Context

### Key Models/Classes
- `Adjustment`
- `AdjustmentKind`
- `AgentAction`
- `AgentBranch`
- `AgentIdentity`
- `AgentLog`
- `AlwaysHardFail`
- `AnthropicSemanticMatcher`
- `AsyncBackendWrapper`
- `AsyncGraphBackend`
- `AuthService`
- `BenchmarkMetrics`
- `BenchmarkSuite`
- `Budget`
- `CommandGate`

### Domain Terms
- AI
- ANY
- APPROVED
- CI
- Convergent Coordination
- Coordination Protocol
- Intent Graph
- JWT
- LGTM
- LICENSE

### Enums/Constants
- `ABSTAIN`
- `ADD_EVIDENCE`
- `ANY`
- `APPEND_ONLY`
- `APPROVE`
- `APPROVED`
- `AUTO_RESOLVE`
- `AdjustmentKind`
- `BLOCK`
- `BLOCKED_BY_CONFLICT`

## Git Conventions

- Commit messages: Conventional commits  (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- Branch naming: `feat/description`, `fix/description`
- Run tests before committing
