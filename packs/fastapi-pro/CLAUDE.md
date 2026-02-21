# CLAUDE.md — {{PROJECT_NAME}}

> {{DESCRIPTION}}

## Quick Reference

- **Version**: {{VERSION}}
- **Python**: >=3.11
- **Framework**: FastAPI + SQLAlchemy + Alembic
- **Database**: PostgreSQL (dev: SQLite)
- **Tests**: pytest + httpx (async)

## Architecture

```
{{PROJECT_NAME}}/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app factory, lifespan, middleware
│   ├── config.py             # Pydantic Settings (env-based)
│   ├── dependencies.py       # Shared DI: get_db, get_current_user
│   ├── models/               # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── base.py           # DeclarativeBase, common mixins
│   │   └── user.py
│   ├── schemas/              # Pydantic request/response models
│   │   ├── __init__.py
│   │   └── user.py
│   ├── services/             # Business logic layer
│   │   ├── __init__.py
│   │   └── user_service.py
│   ├── routers/              # Route handlers (thin — delegate to services)
│   │   ├── __init__.py
│   │   └── users.py
│   └── middleware/           # Custom middleware (auth, logging, CORS)
├── alembic/                  # Database migrations
│   ├── versions/
│   └── env.py
├── tests/
│   ├── conftest.py           # Fixtures: async client, test DB, factories
│   ├── test_users.py
│   └── factories/            # Test data factories
├── alembic.ini
├── pyproject.toml
└── Dockerfile
```

## Coding Standards

### General
- Type hints required on all function signatures — no bare `def f(x):`
- Use `pathlib.Path` everywhere — never `os.path`
- Google-style docstrings on all public functions and classes
- Maximum function length: 50 lines. Extract if longer.
- Imports: stdlib, blank line, third-party, blank line, local

### FastAPI Specific
- All endpoint handlers must be `async def`
- Use dependency injection (`Depends()`) for shared resources (DB, auth, config)
- Request/response bodies use Pydantic schemas — never raw dicts
- Route handlers must be thin: validate input, call service, return response
- Use `status_code=` parameter on decorators, not magic numbers in responses
- Use `HTTPException` with specific status codes, never generic 500
- Background tasks via `BackgroundTasks`, not raw threading

### SQLAlchemy
- Use async sessions (`AsyncSession`) with `async with` context manager
- Define models with `Mapped[]` type annotations (SQLAlchemy 2.0 style)
- Never use `session.commit()` in service layer — commit in the dependency/middleware
- Use `select()` queries, not legacy `session.query()`
- Relationships use `lazy="selectin"` by default to avoid N+1

### Testing
- Use `httpx.AsyncClient` with `ASGITransport` for API tests
- Database tests use a separate test database, rolled back per test
- Use factory functions for test data, not fixtures with hardcoded values
- Test edge cases: empty inputs, duplicate entries, unauthorized access, pagination boundaries
- Coverage target: 90%+ overall, 100% on critical paths (auth, payments)

## Common Commands

```bash
# Development
uvicorn app.main:app --reload --port 8000

# Database
alembic upgrade head                    # Apply migrations
alembic revision --autogenerate -m ""   # Create migration
alembic downgrade -1                    # Rollback one

# Testing
pytest tests/ -v                        # Run all tests
pytest tests/ -v -k "test_users"        # Run specific tests
pytest tests/ --cov=app --cov-report=term-missing

# Linting
ruff check app/ tests/
ruff format app/ tests/
mypy app/

# Docker
docker build -t {{PROJECT_NAME}} .
docker run -p 8000:8000 --env-file .env {{PROJECT_NAME}}
```

## Anti-Patterns (Do NOT Do)

### API Design
- Do NOT return raw dicts from endpoints — always use Pydantic response models
- Do NOT use synchronous database calls in async endpoints
- Do NOT put business logic in route handlers — use service layer
- Do NOT use `*` imports — always import explicitly
- Do NOT catch generic `Exception` in endpoints — let FastAPI handle 500s
- Do NOT use `Query(regex=...)` — use `Query(pattern=...)` (deprecated in 0.100+)

### Database
- Do NOT use `session.execute(text("SELECT ..."))` for queries that can use ORM
- Do NOT call `session.commit()` inside service functions — let the caller/middleware commit
- Do NOT use `session.query()` — use `select()` statements (SQLAlchemy 2.0)
- Do NOT forget to `await` async session operations
- Do NOT use `SERIAL` columns — use `Identity()` or UUID primary keys

### Security
- Do NOT store plaintext passwords — use bcrypt via passlib or direct bcrypt
- Do NOT expose internal error details in production responses
- Do NOT hardcode secrets — use Pydantic Settings with `.env` files
- Do NOT skip CORS configuration — whitelist specific origins
- Do NOT trust client-provided data without validation

### Testing
- Do NOT use `unittest.TestCase` — use plain pytest functions/classes
- Do NOT share database state between tests — isolate with transactions
- Do NOT mock the database in API tests — use a real test database
- Do NOT use `time.sleep()` in tests — use async patterns or mock time

## Dependencies

### Production
- fastapi, uvicorn[standard]
- sqlalchemy[asyncio], asyncpg (or aiosqlite for dev)
- alembic
- pydantic, pydantic-settings
- python-jose[cryptography] (JWT)
- passlib[bcrypt] or bcrypt

### Development
- pytest, pytest-asyncio, httpx
- ruff, mypy
- factory-boy (test factories)

## Environment Variables

```bash
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/dbname
SECRET_KEY=                    # JWT signing key (generate with: openssl rand -hex 32)
ALLOWED_ORIGINS=http://localhost:3000
DEBUG=false
```

## Git Conventions

- Conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
- Branch naming: `feat/description`, `fix/description`
- Run `pytest && ruff check . && ruff format --check .` before pushing
- Squash merge feature branches
