# Show HN Post Draft

**Title:** Show HN: anchormd — Generate CLAUDE.md context files for AI coding agents

**URL:** https://anchormd.dev

**Body:**

Hi HN,

AI coding agents (Claude Code, Cursor, Copilot, Windsurf) work significantly better when they have accurate project context. Each has its own file — `CLAUDE.md`, `.cursorrules`, `.github/copilot-instructions.md`, `.windsurfrules` — that describes your codebase: architecture, conventions, commands, domain terms.

The problem: writing these by hand is tedious and they go stale fast.

anchormd scans your codebase and generates one automatically. It detects your actual coding patterns (naming conventions, import style, quote style) rather than guessing, maps your architecture, finds your test/lint/build commands, and extracts domain context (key classes, API endpoints, enums).

Web UI: paste a GitHub URL at anchormd.dev, get results in ~30 seconds. One-click export to the native format of each agent (Claude, Cursor, Copilot, Windsurf). Sign in with GitHub for private repos and batch-scan your entire account. Repos that already scored 100 and haven't changed get cached on re-scans.

CLI: `pip install anchormd && anchormd generate .`

It scores your context file 0-100. If you're under 100, download a fix report with the exact gap analysis, copy-paste templates for missing sections, and a prompt to paste into Claude Code that fixes everything at once.

Built with Python/FastAPI backend, React frontend. ~700 tests. MIT licensed CLI, Pro tier for advanced features (init, diff, tech-debt scanning). Deep scan reports ($29 one-time) for full architecture audit with recommendations.

Source: https://github.com/Arete-Consortium/anchormd
