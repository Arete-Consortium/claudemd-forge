# CLAUDE.md — ai-skills

## Project Overview

[![Validate Skills](https://github.com/AreteDriver/ai-skills/actions/workflows/validate-skills.yml/badge.svg)](https://github.com/AreteDriver/ai-skills/actions/workflows/validate-skills.yml)
[![Licens

## Current State

- **Language**: Unknown
- **Files**: 159 across 1 languages
- **Lines**: 36,795

## Architecture

```
ai-skills/
├── .github/
│   └── workflows/
├── agents/
│   ├── analysis/
│   ├── browser/
│   ├── email/
│   ├── integrations/
│   ├── orchestration/
│   └── system/
├── decisions/
│   └── templates/
├── docs/
│   └── legacy/
├── examples/
│   └── quickstart/
├── hooks/
├── intel/
├── personas/
│   ├── claude-code/
│   ├── data/
│   ├── devops/
│   ├── domain/
│   ├── engineering/
│   └── security/
├── playbooks/
├── plugins/
│   └── example-quality-gate/
├── prompts/
├── templates/
├── tools/
├── workflows/
│   ├── context-mapping/
│   ├── feature-implementation/
│   └── release-engineering/
├── .gitignore
├── CHANGELOG.md
├── CLAUDE.md
├── LICENSE
├── README.md
├── bundles.yaml
├── registry.yaml
├── workflow-schema.yaml
```

## Tech Stack

- **CI/CD**: GitHub Actions

## Coding Standards

- **Naming**: mixed
- **Line Length (p95)**: 76 characters

## Anti-Patterns (Do NOT Do)

- Do NOT commit secrets, API keys, or credentials
- Do NOT skip writing tests for new code

## Domain Context

### Domain Terms
- ADR
- AI
- ARETE
- Ask Claude
- Building Claude Code
- Bundle Presets Curated
- CD
- CI
- CLAUDE
- CRLF

## Git Conventions

- Commit messages: Conventional commits  (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- Branch naming: `feat/description`, `fix/description`
- Run tests before committing
