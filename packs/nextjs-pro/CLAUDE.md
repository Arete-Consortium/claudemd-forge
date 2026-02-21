# CLAUDE.md — {{PROJECT_NAME}}

> {{DESCRIPTION}}

## Quick Reference

- **Version**: {{VERSION}}
- **Framework**: Next.js 15 (App Router)
- **Language**: TypeScript (strict)
- **Styling**: Tailwind CSS
- **Testing**: Vitest + Playwright

## Architecture

```
{{PROJECT_NAME}}/
├── src/
│   ├── app/                    # App Router pages and layouts
│   │   ├── layout.tsx          # Root layout (metadata, fonts, providers)
│   │   ├── page.tsx            # Home page
│   │   ├── (auth)/             # Auth route group
│   │   │   ├── login/page.tsx
│   │   │   └── register/page.tsx
│   │   ├── dashboard/
│   │   │   ├── layout.tsx      # Dashboard layout (sidebar, auth guard)
│   │   │   └── page.tsx
│   │   └── api/                # Route handlers (API routes)
│   │       └── users/route.ts
│   ├── components/
│   │   ├── ui/                 # Reusable primitives (Button, Input, Modal)
│   │   └── features/           # Feature-specific components
│   ├── lib/                    # Utilities, API clients, helpers
│   │   ├── api.ts              # Fetch wrapper with auth
│   │   ├── auth.ts             # Auth helpers (session, tokens)
│   │   └── utils.ts
│   ├── hooks/                  # Custom React hooks
│   ├── types/                  # TypeScript type definitions
│   └── styles/                 # Global styles (Tailwind base)
├── public/                     # Static assets
├── tests/
│   ├── unit/                   # Vitest unit tests
│   └── e2e/                    # Playwright E2E tests
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
└── package.json
```

## Coding Standards

### General
- TypeScript strict mode — no `any`, no implicit returns
- Named exports only — no `export default`
- File naming: `kebab-case.tsx` for components, `camelCase.ts` for utilities
- Max component length: 150 lines. Extract sub-components if longer.
- Imports: react, blank, next, blank, third-party, blank, local (use `@/` alias)

### React / Next.js
- Server Components by default — only add `'use client'` when genuinely needed
- Data fetching in Server Components with `async/await` — no `useEffect` for initial data
- Use Server Actions for mutations — no API routes for simple form submissions
- Use `next/image` for all images, `next/link` for navigation, `next/font` for fonts
- Metadata via `generateMetadata()` or static `metadata` export — not `<Head>`
- Use route groups `(name)` for layout organization without URL impact
- Loading states via `loading.tsx`, errors via `error.tsx` boundary files

### State Management
- Server state: fetch in Server Components, pass as props
- Client state: `useState` for local, React Context for shared
- Form state: `useActionState` with Server Actions
- URL state: `useSearchParams` for filters/pagination
- No Redux unless state is genuinely complex and cross-cutting

### Styling
- Tailwind CSS utility classes — no inline `style={{}}` objects
- Extract repeated patterns to `@apply` in CSS modules or component variants
- Use `cn()` utility (clsx + twMerge) for conditional classes
- Responsive: mobile-first (`sm:`, `md:`, `lg:` breakpoints)
- Dark mode via `dark:` variant with `class` strategy

### Testing
- Vitest for unit tests (components, hooks, utilities)
- Playwright for E2E tests (critical user flows)
- Use `@testing-library/react` for component tests
- Mock `fetch` with MSW (Mock Service Worker), not manual mocks
- Test accessibility with `@axe-core/playwright`

## Common Commands

```bash
# Development
npm run dev                             # Start dev server (port 3000)
npm run build && npm start              # Production build + start

# Testing
npm test                                # Vitest unit tests
npx playwright test                     # E2E tests
npx playwright test --ui                # E2E with interactive UI

# Linting
npm run lint                            # ESLint
npx tsc --noEmit                        # TypeScript check
npx prettier --check .                  # Format check

# Analysis
npx @next/bundle-analyzer              # Bundle size analysis
npx lighthouse http://localhost:3000    # Performance audit
```

## Anti-Patterns (Do NOT Do)

### Architecture
- Do NOT use Pages Router patterns (`getServerSideProps`, `getStaticProps`) in App Router
- Do NOT put `'use client'` at the top of every file — Server Components are the default
- Do NOT use `useEffect` for initial data loading — fetch in Server Components
- Do NOT create API routes for simple CRUD — use Server Actions
- Do NOT import server-only code in Client Components

### React
- Do NOT use class components — functional components with hooks only
- Do NOT use `any` type — define proper interfaces in `types/`
- Do NOT mutate state directly — use immutable update patterns
- Do NOT use `useEffect` for derived state — use `useMemo` or compute inline
- Do NOT prop-drill more than 2 levels — use Context or composition

### Performance
- Do NOT import large libraries in Client Components without dynamic import
- Do NOT use unoptimized `<img>` tags — use `next/image`
- Do NOT fetch data client-side when server-side works (SSR/SSG)
- Do NOT skip `loading.tsx` for routes with data fetching
- Do NOT use `useEffect` + `useState` for data that can be a Server Component

### Security
- Do NOT expose API keys in client-side code — use server-side env vars
- Do NOT trust `searchParams` without validation — sanitize all URL inputs
- Do NOT use `dangerouslySetInnerHTML` without sanitization
- Do NOT skip CSRF protection on mutation endpoints

## Environment Variables

```bash
# Public (available in browser — prefix with NEXT_PUBLIC_)
NEXT_PUBLIC_APP_URL=http://localhost:3000
NEXT_PUBLIC_API_URL=http://localhost:8000

# Server-only (never exposed to browser)
DATABASE_URL=postgresql://...
AUTH_SECRET=                    # Generate: openssl rand -base64 32
STRIPE_SECRET_KEY=sk_...
```

## Git Conventions

- Conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
- Run `npm run lint && npx tsc --noEmit && npm test` before pushing
- Squash merge feature branches
