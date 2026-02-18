# CLAUDE.md — Win-the-week-planner

## Project Overview

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

## Current State

- **Version**: 0.0.0
- **Language**: JavaScript
- **Files**: 29 across 3 languages
- **Lines**: 6,124

## Architecture

```
Win-the-week-planner/
├── public/
├── src/
│   ├── __tests__/
│   └── components/
├── .gitignore
├── README.md
├── eslint.config.js
├── index.html
├── package-lock.json
├── package.json
├── vite.config.js
```

## Tech Stack

- **Language**: JavaScript, CSS, HTML
- **Framework**: react
- **Package Manager**: npm
- **Linters**: eslint
- **Test Frameworks**: jest, vitest

## Coding Standards

- **Naming**: camelCase
- **Quote Style**: double quotes
- **Semicolons**: required
- **Line Length (p95)**: 97 characters

## Common Commands

```bash
# dev
npm run dev
# build
npm run build
# lint
npm run lint
# preview
npm run preview
# test
npm run test
# test:watch
npm run test:watch
```

## Anti-Patterns (Do NOT Do)

- Do NOT commit secrets, API keys, or credentials
- Do NOT skip writing tests for new code
- Do NOT use class components — use functional components with hooks
- Do NOT mutate state directly — use immutable patterns
- Do NOT use `useEffect` for derived state — use `useMemo`

## Dependencies

### Core
- react
- react-dom

### Dev
- @eslint/js
- @testing-library/jest-dom
- @testing-library/react
- @types/react
- @types/react-dom
- @vitejs/plugin-react
- eslint
- eslint-plugin-react-hooks
- eslint-plugin-react-refresh
- globals

## Domain Context

### Domain Terms
- Fast Refresh
- HMR
- React Compiler The React Compiler
- SWC
- TS
- Vite This

## Git Conventions

- Commit messages: Conventional commits  (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- Branch naming: `feat/description`, `fix/description`
- Run tests before committing
