# CLAUDE.md — lobster

## Project Overview

Workflow runtime for AI agents - deterministic pipelines with approval gates

## Current State

- **Version**: 2026.1.21-1
- **Language**: TypeScript
- **Files**: 83 across 2 languages
- **Lines**: 7,941

## Architecture

```
lobster/
├── bin/
├── src/
│   ├── commands/
│   ├── recipes/
│   ├── renderers/
│   ├── sdk/
│   ├── state/
│   └── workflows/
├── test/
│   └── fixtures/
├── .gitignore
├── .oxlintrc.json
├── CHANGELOG.md
├── LICENSE
├── README.md
├── VISION.md
├── package.json
├── pnpm-lock.yaml
├── tsconfig.json
```

## Tech Stack

- **Language**: TypeScript, JavaScript
- **Package Manager**: pnpm
- **Type Checkers**: tsc

## Coding Standards

- **Naming**: camelCase
- **Quote Style**: single quotes
- **Semicolons**: required
- **Line Length (p95)**: 85 characters

## Common Commands

```bash
# clean
npm run clean
# build
npm run build
# prepack
npm run prepack
# typecheck
npm run typecheck
# lint
npm run lint
# fmt
npm run fmt
# test
npm run test
```

## Anti-Patterns (Do NOT Do)

- Do NOT commit secrets, API keys, or credentials
- Do NOT skip writing tests for new code
- Do NOT use `any` type — define proper type interfaces
- Do NOT use `var` — use `const` or `let`

## Dependencies

### Core
- ajv
- yaml

### Dev
- @types/node
- oxlint
- typescript

## Domain Context

### Key Models/Classes
- `Lobster`

### Domain Terms
- AI
- JSON
- MERGEABLE
- MERGED
- OPEN
- OS
- PR
- TTY
- UNKNOWN
- YAML

## Git Conventions

- Commit messages: Conventional commits  (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- Branch naming: `feat/description`, `fix/description`
- Run tests before committing
