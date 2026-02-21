# CLAUDE.md — {{PROJECT_NAME}}

> {{DESCRIPTION}}

## Quick Reference

- **Version**: {{VERSION}}
- **Framework**: Django 5 + Django REST Framework
- **Database**: PostgreSQL
- **Task Queue**: Celery + Redis
- **Testing**: pytest-django

## Architecture

```
{{PROJECT_NAME}}/
├── config/                     # Project configuration
│   ├── __init__.py
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py            # Shared settings
│   │   ├── development.py     # Dev overrides (DEBUG=True)
│   │   └── production.py      # Prod settings (env-based)
│   ├── urls.py                # Root URL configuration
│   ├── wsgi.py
│   └── celery.py              # Celery app configuration
├── apps/
│   ├── users/                 # User management app
│   │   ├── models.py
│   │   ├── serializers.py     # DRF serializers
│   │   ├── views.py           # DRF viewsets
│   │   ├── urls.py
│   │   ├── admin.py
│   │   ├── services.py        # Business logic
│   │   ├── tasks.py           # Celery tasks
│   │   └── tests/
│   │       ├── test_models.py
│   │       ├── test_views.py
│   │       └── factories.py   # factory_boy factories
│   └── core/                  # Shared utilities
│       ├── models.py          # Abstract base models (timestamps, soft delete)
│       ├── permissions.py     # Custom DRF permissions
│       └── pagination.py      # Custom pagination classes
├── templates/                 # Django templates (if any)
├── static/                    # Static files
├── requirements/
│   ├── base.txt
│   ├── development.txt
│   └── production.txt
├── manage.py
├── pyproject.toml
├── Dockerfile
└── docker-compose.yml
```

## Coding Standards

### General
- Type hints on all function signatures — use `django-stubs` for Django types
- Google-style docstrings on all public functions and classes
- Maximum function length: 40 lines. Extract to service layer if longer
- Use `pathlib.Path` everywhere — never `os.path`
- Settings: no hardcoded values — use `env()` from django-environ

### Models
- Always define `__str__()` and `Meta.ordering`
- Use `UUIDField` for public-facing IDs, `AutoField` for internal PKs
- Abstract base model for `created_at` / `updated_at` timestamps
- Use `constraints` in `Meta` for database-level validation
- Indexes on frequently queried fields via `Meta.indexes`

### Views / Serializers (DRF)
- Use `ModelViewSet` for standard CRUD, `APIView` for custom logic
- Serializers validate input — views orchestrate, services execute
- Use `select_related()` / `prefetch_related()` in querysets to avoid N+1
- Custom permissions in `permissions.py`, not inline in views
- Pagination on all list endpoints — use `PageNumberPagination` or cursor

### Services
- Business logic lives in `services.py`, not in views or models
- Services receive validated data (dicts/dataclasses), not raw request data
- Services return domain objects, not HTTP responses
- Wrap multi-step operations in `transaction.atomic()`
- Log business events with structured logging

### Testing
- Use `pytest-django` with `@pytest.mark.django_db`
- Use `factory_boy` for test data — never fixtures or raw `Model.objects.create`
- Test the API contract (status codes, response shape), not implementation
- Use `APIClient` for API tests, not Django's `TestCase.client`
- Separate unit tests (services) from integration tests (views)

## Common Commands

```bash
# Development
python manage.py runserver                        # Dev server
python manage.py shell_plus                       # Enhanced shell (django-extensions)

# Database
python manage.py makemigrations                   # Create migration
python manage.py migrate                          # Apply migrations
python manage.py showmigrations                   # Migration status

# Testing
pytest                                            # All tests
pytest apps/users/ -v                             # Single app
pytest --cov=apps --cov-report=term-missing       # With coverage

# Linting
ruff check apps/ config/
ruff format apps/ config/
mypy apps/

# Celery
celery -A config worker -l info                   # Start worker
celery -A config beat -l info                     # Start scheduler

# Docker
docker compose up -d                              # Start services
docker compose exec web python manage.py migrate  # Run migrations in container
```

## Anti-Patterns (Do NOT Do)

### Architecture
- Do NOT put business logic in views — delegate to services
- Do NOT use function-based views for CRUD — use DRF viewsets
- Do NOT use `settings.py` as a single file — split into base/dev/prod
- Do NOT import models across apps — use signals or service layer
- Do NOT use raw SQL when the ORM handles it

### Models
- Do NOT use `Model.objects.all()` without pagination in views
- Do NOT skip migrations — always run `makemigrations` after model changes
- Do NOT use `null=True` on string fields — use `blank=True, default=""`
- Do NOT define business logic in model methods — use services
- Do NOT use `ForeignKey(on_delete=CASCADE)` without considering the impact

### Performance
- Do NOT query the database in loops — use `bulk_create`, `bulk_update`
- Do NOT skip `select_related()` / `prefetch_related()` — causes N+1 queries
- Do NOT use `Model.objects.count()` for existence checks — use `.exists()`
- Do NOT load entire querysets into memory — use `.iterator()` for large sets
- Do NOT use synchronous I/O in async views — use `sync_to_async()`

### Security
- Do NOT hardcode `SECRET_KEY` — generate per environment
- Do NOT use `DEBUG=True` in production
- Do NOT trust user input in `extra()` or `raw()` queries — SQL injection risk
- Do NOT expose internal model IDs in URLs — use UUIDs
- Do NOT skip CSRF middleware for non-API views

### Testing
- Do NOT use Django fixtures (JSON/YAML) — use factory_boy
- Do NOT share test data between test methods — isolate everything
- Do NOT test Django internals (ORM, auth) — test your business logic
- Do NOT use `TransactionTestCase` unless testing transaction behavior

## Environment Variables

```bash
DJANGO_SETTINGS_MODULE=config.settings.production
SECRET_KEY=                    # Generate: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
DATABASE_URL=postgresql://user:pass@localhost:5432/dbname
REDIS_URL=redis://localhost:6379/0
ALLOWED_HOSTS=example.com,www.example.com
CORS_ALLOWED_ORIGINS=https://frontend.example.com
```

## Git Conventions

- Conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
- Run `pytest && ruff check . && ruff format --check .` before pushing
- Squash merge feature branches
