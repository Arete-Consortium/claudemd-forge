# Show HN Post Draft

**Title:** Show HN: anchormd — Generate CLAUDE.md context files for AI coding agents

**URL:** https://anchormd.dev

**Body:**

Hi HN,

AI coding agents (Claude Code, Cursor, Copilot) work significantly better when they have accurate project context. The standard approach is a CLAUDE.md or .cursorrules file that describes your codebase — architecture, conventions, commands, domain terms.

The problem: writing these by hand is tedious and they go stale fast.

anchormd scans your codebase and generates one automatically. It detects your actual coding patterns (naming conventions, import style, quote style) rather than guessing, maps your architecture, finds your test/lint/build commands, and extracts domain context (key classes, API endpoints, enums).

Web UI: paste a GitHub URL at anchormd.dev, get results in ~30 seconds. Sign in with GitHub for private repos and batch-scan your entire account.

CLI: `pip install anchormd && anchormd generate .`

It also audits existing context files and scores them 0-100 with specific improvement recommendations.

Built with Python/FastAPI backend, React frontend. 693 tests. MIT licensed CLI, Pro tier for advanced features (init, diff, tech-debt scanning).

Source: https://github.com/Arete-Consortium/anchormd
