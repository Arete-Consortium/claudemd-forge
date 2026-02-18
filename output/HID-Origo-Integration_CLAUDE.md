# CLAUDE.md — HID-Origo-Integration

## Project Overview

**Objective**: Enable employee badges in Apple and Google Wallet using HID Origo platform

## Current State

- **Language**: Python
- **Files**: 19 across 1 languages
- **Lines**: 2,566

## Architecture

```
HID-Origo-Integration/
├── .github/
├── docs/
├── src/
│   ├── api/
│   ├── models/
│   ├── services/
│   └── utils/
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
├── requirements.txt
```

## Tech Stack

- **Language**: Python
- **Framework**: flask
- **Package Manager**: pip

## Coding Standards

- **Naming**: snake_case
- **Quote Style**: double quotes
- **Type Hints**: present
- **Docstrings**: google style
- **Imports**: mixed
- **Path Handling**: mixed
- **Line Length (p95)**: 70 characters

## Anti-Patterns (Do NOT Do)

- Do NOT commit secrets, API keys, or credentials
- Do NOT skip writing tests for new code
- Do NOT use `os.path` — use `pathlib.Path` everywhere
- Do NOT use bare `except:` — catch specific exceptions
- Do NOT use mutable default arguments
- Do NOT use `print()` for logging — use the `logging` module

## Dependencies

### Core
- flask

## Domain Context

### Key Models/Classes
- `CallbackAPI`
- `CallbackRecovery`
- `CallbackRegistration`
- `CloudEvent`
- `CredentialManagementAPI`
- `EventFilter`
- `EventType`
- `IssuanceToken`
- `MockCallbackAPI`
- `MockCredentialManagementAPI`
- `MockOrigoAuth`
- `MockUserManagementAPI`
- `OrigoAuth`
- `OrigoConfig`
- `Pass`

### Domain Terms
- ACME
- Access Control System
- Apple Wallet
- Corporate Identity Provider
- Corporate Mobile Badge Integration
- Credential Management
- Exercise Parts
- Google Wallet
- HID
- Integration Requirements

### Enums/Constants
- `ACTIVE`
- `CANCELLED`
- `CREDENTIAL_RESUMED`
- `CREDENTIAL_SUSPENDED`
- `DELETED`
- `FLASK_WEBHOOK_EXAMPLE`
- `PASS_CREATED`
- `PASS_DELETED`
- `PASS_PROVISIONED`
- `PASS_TEMPLATE_ID`

## Git Conventions

- Commit messages: Conventional commits  (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- Branch naming: `feat/description`, `fix/description`
- Run tests before committing
