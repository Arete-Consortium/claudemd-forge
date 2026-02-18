# CLAUDE.md — Chefwise

## Project Overview

AI-powered recipe suggestion and meal planning app

## Current State

- **Version**: 0.1.0
- **Language**: JavaScript
- **Files**: 350 across 9 languages
- **Lines**: 44,305

## Architecture

```
Chefwise/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   └── workflows/
├── android/
│   ├── app/
│   └── gradle/
├── assets/
├── chefwise/
│   ├── ai/
│   ├── api/
│   ├── app/
│   ├── config/
│   ├── database/
│   └── models/
├── coverage/
│   └── lcov-report/
├── docs/
│   └── adr/
├── e2e/
├── functions/
├── icons/
├── ios/
│   └── App/
├── mobile/
│   ├── docs/
│   ├── lib/
│   └── scripts/
├── public/
│   ├── icons/
│   └── locales/
├── src/
│   ├── __tests__/
│   ├── app/
│   ├── components/
│   ├── contexts/
│   ├── firebase/
│   ├── hooks/
│   ├── middleware/
│   ├── prompts/
│   ├── styles/
│   └── utils/
├── tests/
├── .env.example
├── .firebaserc
├── .gitignore
├── ARCHITECTURE.md
├── CLAUDE_ANDROID_BUILD.md
├── CONTRIBUTING.md
├── IMPLEMENTATION_COMPLETE.md
├── IMPLEMENTATION_NOTES.md
├── IMPLEMENTATION_SUMMARY.md
├── LICENSE
├── MOBILE_APP_COMPLETION.md
├── NAVIGATION.md
├── PROJECT_OVERVIEW.md
├── QUICKSTART.md
├── README.md
├── REFACTORING_SUMMARY.md
├── REPOSITORY_SETUP.md
├── SUBSCRIPTION_SETUP.md
├── capacitor.config.ts
├── eslint.config.mjs
├── firebase.json
├── firestore.indexes.json
├── firestore.rules
├── jest.config.js
├── jest.setup.js
├── next-env.d.ts
├── next-i18next.config.js
├── next.config.js
├── package.json
├── playwright.config.js
├── postcss.config.js
├── pyproject.toml
├── requirements.txt
├── storage.rules
├── tailwind.config.js
├── tsconfig.json
```

## Tech Stack

- **Language**: JavaScript, Dart, Python, Java, CSS, TypeScript, HTML, Swift, Shell
- **Framework**: fastapi, nextjs, react
- **Package Manager**: npm, pip
- **Linters**: eslint
- **Type Checkers**: tsc
- **Test Frameworks**: jest, pytest
- **CI/CD**: GitHub Actions

## Coding Standards

- **Naming**: camelCase
- **Quote Style**: single quotes
- **Semicolons**: required
- **Line Length (p95)**: 72 characters

## Common Commands

```bash
# dev
npm run dev
# build
npm run build
# start
npm run start
# lint
npm run lint
# test
npm run test
# test:e2e
npm run test:e2e
# test:e2e:ui
npm run test:e2e:ui
# test:e2e:headed
npm run test:e2e:headed
# ios:build
npm run ios:build
# ios:open
npm run ios:open
# android:build
npm run android:build
# android:open
npm run android:open

# test
pytest tests/ -v
```

## Anti-Patterns (Do NOT Do)

- Do NOT commit secrets, API keys, or credentials
- Do NOT skip writing tests for new code
- Do NOT use `any` type — define proper type interfaces
- Do NOT use `var` — use `const` or `let`
- Do NOT use synchronous database calls in async endpoints
- Do NOT return raw dicts — use Pydantic response models
- Do NOT use class components — use functional components with hooks
- Do NOT mutate state directly — use immutable patterns
- Do NOT use `useEffect` for derived state — use `useMemo`
- Do NOT use `os.path` — use `pathlib.Path` everywhere
- Do NOT use bare `except:` — catch specific exceptions
- Do NOT use mutable default arguments
- Do NOT use `print()` for logging — use the `logging` module

## Dependencies

### Core
- fastapi
- uvicorn
- streamlit
- openai
- pydantic
- pydantic-settings
- sqlalchemy
- python-dotenv

### Dev
- pytest
- pytest-asyncio
- httpx

## Domain Context

### Key Models/Classes
- `Base`
- `CacheManager`
- `DietaryRestriction`
- `ErrorBoundary`
- `Ingredient`
- `MealPlan`
- `MealPlanCreate`
- `MealPlanRepository`
- `MealPlanService`
- `MealPlanTable`
- `MealSlot`
- `MealSlotTable`
- `MealType`
- `MemoryCache`
- `OpenAIClient`

### Domain Terms
- AI
- BEGIN
- CSS
- Chat Chat
- Configuration Create
- END
- Firebase Admin
- Firebase Cloud Functions
- GPT
- KEY

### Enums/Constants
- `BREAKFAST`
- `DAIRY_FREE`
- `DINNER`
- `GLUTEN_FREE`
- `INGREDIENT_SUBSTITUTION_USER`
- `KETO`
- `LOW_CARB`
- `LUNCH`
- `MEAL_PLAN_SYSTEM`
- `MEAL_PLAN_USER`

### Outstanding Items
- **NOTE**: This file should not be edited (`next-env.d.ts`)

## Git Conventions

- Commit messages: Conventional commits  (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- Branch naming: `feat/description`, `fix/description`
- Run tests before committing
