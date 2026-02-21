# ClaudeMD Forge

> Generate optimized CLAUDE.md files for AI coding agents in seconds.

Stop hand-rolling CLAUDE.md. Let Forge analyze your codebase and generate
a production-grade configuration file that makes Claude Code, Cursor,
Windsurf, and Codex actually understand your project.

## Why?

AI coding agents are only as good as the context you give them. A well-crafted
CLAUDE.md is the difference between an agent that writes idiomatic code and one
that fights your conventions on every change.

ClaudeMD Forge:
- **Scans** your codebase to detect languages, frameworks, and patterns
- **Generates** a complete CLAUDE.md with coding standards, commands, and anti-patterns
- **Audits** existing CLAUDE.md files and scores them against best practices
- **Framework-aware** presets for React, FastAPI, Rust, Django, Next.js, and more

## Install

```bash
pip install claudemd-forge
```

## Quick Start

```bash
# Generate a CLAUDE.md for your project
claudemd-forge generate .

# Audit an existing CLAUDE.md
claudemd-forge audit ./CLAUDE.md

# Interactive setup
claudemd-forge init .

# See what would change
claudemd-forge diff .

# List available presets
claudemd-forge presets

# List framework-specific presets
claudemd-forge frameworks
```

## Example Output

Running `claudemd-forge generate .` on a FastAPI project produces:

```markdown
# CLAUDE.md — my-api

## Project Overview
my-api — TODO: Add project description.

## Current State
- **Version**: 0.1.0
- **Language**: Python
- **Files**: 47 across 2 languages
- **Lines**: 3,204

## Tech Stack
- **Language**: Python
- **Framework**: fastapi
- **Package Manager**: pip
- **Linters**: ruff
- **Test Frameworks**: pytest
- **CI/CD**: GitHub Actions

## Coding Standards
- **Naming**: snake_case
- **Type Hints**: present
- **Docstrings**: google style
- **Imports**: absolute

## Common Commands
...

## Anti-Patterns (Do NOT Do)
- Do NOT use synchronous database calls in async endpoints
- Do NOT return raw dicts — use Pydantic response models
- Do NOT use `os.path` — use `pathlib.Path` everywhere
...
```

## GitHub Action

Add automated CLAUDE.md auditing to your CI pipeline:

```yaml
# .github/workflows/claudemd-audit.yml
name: Audit CLAUDE.md
on: [pull_request]

jobs:
  audit:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
    steps:
      - uses: actions/checkout@v6
      - uses: Arete-Consortium/claudemd-forge@v0.1.0
        with:
          fail-below: 40     # Minimum passing score (0-100)
          comment: true       # Post results as PR comment
```

The action posts a formatted comment on your PR with score, findings, and recommendations.

## Free vs Pro

| Feature | Free | Pro ($8/mo) |
|---------|:----:|:-----------:|
| `generate` — scan and produce CLAUDE.md | Yes | Yes |
| `audit` — score existing CLAUDE.md | Yes | Yes |
| 11 community presets (FastAPI, React, Rust, Django...) | Yes | Yes |
| `init` — interactive guided setup | - | Yes |
| `diff` — detect drift between CLAUDE.md and codebase | - | Yes |
| CI integration — GitHub Action auto-audit on PR | - | Yes |
| 6 premium presets (monorepo, data-science, devops...) | - | Yes |
| Team templates (shared org standards) | - | Planned |

**Activate Pro:**
```bash
export CLAUDEMD_FORGE_LICENSE=CMDF-XXXX-XXXX-XXXX
```

## Framework Presets

| Preset | Description |
|--------|-------------|
| `python-fastapi` | FastAPI + async patterns |
| `python-cli` | Python CLI with typer/click |
| `react-typescript` | React + TypeScript + hooks |
| `nextjs` | Next.js App Router conventions |
| `django` | Django with ORM patterns |
| `rust` | Rust with clippy + proper error handling |
| `go` | Go with standard project layout |
| `node-express` | Express.js backend |

## Audit Scoring

Forge scores your CLAUDE.md on:
- **Section coverage** — does it have the essentials?
- **Accuracy** — does it match your actual codebase?
- **Specificity** — are instructions actionable or vague?
- **Anti-patterns** — does it prevent common mistakes?
- **Freshness** — is it up to date?

## Development

```bash
# Clone and install
git clone https://github.com/Arete-Consortium/claudemd-forge.git
cd claudemd-forge
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Lint
ruff check src/ tests/
ruff format src/ tests/
```

## License

MIT
