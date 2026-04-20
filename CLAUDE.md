# CLAUDE.md — anchormd

## Project Overview

Generate and audit CLAUDE.md files for AI coding agents. Freemium CLI with Pro license server and Stripe-automated fulfillment.

Commands: `generate`, `audit` (structure scoring), `verify` (reality check — claims vs filesystem), `fleet` (cross-repo audit), `harvest` (recurring gotchas from Claude Code transcripts), `patch` (splice harvested anti-patterns into existing CLAUDE.md), plus Pro: `init`, `diff`, `tech-debt`, `github-health`, `cleanup`, `drift`.

## Current State

- **Version**: 0.5.0
- **Language**: Python
- **Tests**: 134 (license server) + ~390 client-side tests (including verify/fleet/harvest/patch/suggestions)
- **License Server**: `https://cmdf-license.fly.dev` (Fly.io, SQLite + WAL)
- **Stripe**: Live — automated checkout → key generation → email delivery

## Monetization

- **Free**: `generate`, `audit`, 11 community presets
- **Pro ($8/mo or $69/yr)**: `init`, `diff`, CI integration, 6 premium presets, team templates
- **Template Packs**: Gumroad ($5-10 each)
- **Payment Links**: Stripe Payment Links → webhook → auto key + email
- **Do NOT modify pricing without explicit approval**

## Architecture

```
anchormd/
├── .github/workflows/
├── docs/
├── license_server/           # FastAPI license server (separate deployable)
│   ├── migrations/           # SQLite schema migrations
│   ├── routes/
│   │   ├── activate.py       # POST /v1/activate (admin)
│   │   ├── validate.py       # POST /v1/validate
│   │   ├── revoke.py         # POST /v1/revoke (admin)
│   │   └── webhook.py        # POST /v1/webhooks/stripe
│   ├── stripe_webhooks.py    # Event handlers (checkout, cancel, payment_failed)
│   ├── email_delivery.py     # SMTP license key delivery
│   ├── key_gen.py            # ANMD-XXXX-XXXX-XXXX generation + hashing
│   ├── config.py             # Env var configuration
│   ├── database.py           # SQLite connection + migration runner
│   ├── models.py             # Pydantic request/response models
│   ├── rate_limit.py         # slowapi rate limiter
│   ├── Dockerfile            # Multi-stage build for Fly.io
│   ├── fly.toml              # Fly.io deployment config
│   └── requirements.txt      # Server dependencies
├── output/
├── packs/                    # Gumroad template packs
├── prompts/
├── scripts/
│   ├── stripe_setup.py       # Create Stripe products/prices/payment links
│   └── keygen.py             # Manual key generation (legacy)
├── src/anchormd/       # CLI package (PyPI: anchormd)
│   ├── licensing.py          # Client-side key detection, validation, caching
│   ├── machine_id.py         # Hostname+username hash
│   ├── gates.py              # @require_pro feature gating
│   └── cli.py                # Typer CLI
├── tests/
│   ├── drift/
│   └── license_server/
├── web/                         # Phase 1 Web UI (anchormd-web on Fly.io)
│   ├── app.py                   # FastAPI: POST /api/scan, GET /api/scan/{id}
│   ├── generator.py             # Wrapper around anchormd generation logic
│   ├── frontend/                # React + Vite + Tailwind (dark theme)
│   └── Dockerfile               # Multi-stage build (Node + Python)
├── fly.web.toml                 # Fly.io config for anchormd-web (deploy from project root)
├── .dockerignore
├── pyproject.toml
```

## Tech Stack

- **Language**: Python, HTML, SQL
- **Package Manager**: pip
- **Linters**: ruff
- **Formatters**: ruff
- **Type Checkers**: mypy
- **Test Frameworks**: pytest
- **CI/CD**: GitHub Actions
- **Hosting**: Fly.io (license server), PyPI (CLI)
- **Payments**: Stripe (webhooks + payment links)
- **Email**: SMTP (Gmail app password)

## API Endpoints (License Server)

| Endpoint | Auth | Rate Limit | Purpose |
|----------|------|------------|---------|
| `GET /v1/health` | None | 120/min | Health check + license counts |
| `POST /v1/activate` | Admin Bearer | 10/min | Create license key |
| `POST /v1/validate` | None | 60/min | Validate license key |
| `POST /v1/revoke` | Admin Bearer | 10/min | Revoke license key |
| `POST /v1/usage/check` | None | 60/min | Check scan quota remaining |
| `POST /v1/usage` | None | 30/min | Record a scan + return updated quota |
| `POST /v1/webhooks/stripe` | Stripe signature | 30/min | Automated fulfillment |

## License Key System

- **Format**: `ANMD-XXXX-XXXX-XXXX` (uppercase alphanumeric)
- **Checksum**: Segment 3 = first 4 hex chars of `SHA256("anchormd-v1:{seg1}-{seg2}")`
- **Storage**: SHA-256 hash only — plaintext never stored
- **Masking**: `ANMD-****-****-{last4}` for display
- **Client detection**: `ANCHORMD_LICENSE` env var → `.anchormd-license` → `~/.config/anchormd/license`
- **Validation**: Local checksum → server call (5s timeout) → 24h cache → fail-open to local-only

## Environment Variables

### License Server (Fly.io secrets)
- `ANMD_ADMIN_SECRET` — Bearer token for admin endpoints
- `ANMD_DB_PATH` — SQLite path (default: `/data/license_server.db`)
- `STRIPE_SECRET_KEY` — Stripe API key
- `STRIPE_WEBHOOK_SECRET` — Stripe webhook signing secret
- `ANMD_SMTP_USER` — Gmail address
- `ANMD_SMTP_PASSWORD` — Gmail app password
- `ANMD_SMTP_FROM` — From address for emails

### Client (user-side)
- `ANCHORMD_LICENSE` — License key
- `ANCHORMD_LICENSE_SERVER` — Server URL (optional)

## Common Commands

```bash
# test (all)
.venv/bin/python -m pytest tests/ -v
# test (license server only)
.venv/bin/python -m pytest tests/license_server/ -v
# lint
ruff check src/ tests/ license_server/
# format
ruff format src/ tests/ license_server/
# type check
mypy src/
# deploy license server
fly deploy --dockerfile license_server/Dockerfile --config license_server/fly.toml
# health check
curl https://cmdf-license.fly.dev/v1/health
```

## Coding Standards

- **Naming**: snake_case
- **Quote Style**: double quotes
- **Type Hints**: present
- **Imports**: absolute
- **Path Handling**: pathlib
- **Line Length**: 100 characters
- **Error Handling**: Custom exception classes, `from exc` in re-raises

## Anti-Patterns (Do NOT Do)

- Do NOT commit secrets, API keys, or credentials
- Do NOT skip writing tests for new code
- Do NOT use `os.path` — use `pathlib.Path` everywhere
- Do NOT use bare `except:` — catch specific exceptions
- Do NOT use mutable default arguments
- Do NOT use `print()` for logging — use the `logging` module
- Do NOT store plaintext license keys in the database
- Do NOT modify pricing tiers without approval

## Dependencies

### CLI (PyPI)
- typer, rich, pydantic, tomli, pyyaml, jinja2
- httpx (optional, for server validation)

### License Server (Fly.io)
- fastapi, uvicorn, pydantic, slowapi, stripe

### Dev
- pytest, mypy, ruff, httpx

## Web UI Roadmap (April 2026 Sprint)

**Strategic context:** Claude Code adoption is accelerating. Every user needs a CLAUDE.md. Most write poor ones. anchormd is the tool that fixes that.

**Revenue targets:**
- Free tier: Single repo scan, basic CLAUDE.md output
- Pro ($8/mo or $69/yr): Full audit, multi-repo, PR integration, history (existing)
- One-time ($29): Single deep repo scan with recommendations (new web product)

### Phase 1 — MVP Web UI (April 1–14)
Goal: GitHub URL in → CLAUDE.md out. No auth, no payment. Shareable link.
- FastAPI endpoint: `POST /scan` — accepts GitHub repo URL, returns generated CLAUDE.md
- Port generation logic from CLI to `web/generator.py`
- React landing page: URL input → loading → output with copy button
- Deploy on Fly.io

**Done when:** A stranger can paste a public GitHub URL and get a usable CLAUDE.md in under 30 seconds.

### Phase 2 — Stripe Gate (April 14–21)
Goal: Paywalled audit feature. First dollar from web product.
- Stripe Checkout — one-time $29 deep scan
- Email delivery of audit report (no auth required yet)

### Phase 3 — Distribution (April 21–28)
Goal: First 100 users. First 3 paying customers.
- r/ClaudeAI, r/cursor, r/LocalLLaMA, Show HN, X/Twitter, Substack

### Phase 4 — Subscription + Auth (April 28–May 12)
Goal: Recurring revenue. Multi-repo. PR integration.
- GitHub OAuth
- Multi-repo dashboard
- GitHub PR creation: push generated CLAUDE.md directly to repo

### Key Decisions

| Decision | Rationale |
|----------|-----------|
| Web UI over CLI-only | CLI has low monetization ceiling; web enables Stripe gate |
| One-time $29 before subscription | Lowest friction first purchase; validate willingness to pay |
| Fly.io deployment | Consistent with existing infra |

### IP Notes
- Core generation algorithm (repo structure → CLAUDE.md schema) is proprietary
- Audit ruleset (anti-patterns, gap detection) is proprietary
- Do not open-source the API or web layer; CLI can remain MIT

---

## Git Conventions

- Commit messages: Conventional commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- Branch naming: `feat/description`, `fix/description`
- Run tests before committing
