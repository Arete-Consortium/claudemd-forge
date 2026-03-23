# Substack Post Draft

**Title:** Why Your AI Coding Agent Is Hallucinating (And How to Fix It in 30 Seconds)

---

If you're using Claude Code, Cursor, or GitHub Copilot, you've probably noticed: sometimes the AI nails it, sometimes it generates code that doesn't match your project at all.

The difference isn't the model. It's context.

## The CLAUDE.md Problem

AI coding agents need a context file — a description of your project that tells them how things work. Claude Code uses `CLAUDE.md`. Cursor uses `.cursorrules`. Without one, the AI is guessing.

Most developers either:
1. Don't have one (the AI guesses everything)
2. Wrote one once and it's now stale
3. Copied a template that doesn't match their actual code

## The Fix

I built [anchormd](https://anchormd.dev) to solve this. It scans your actual codebase and generates an accurate context file in ~30 seconds.

What it detects from your code (not templates):
- **Naming conventions** — snake_case? camelCase? It reads your files
- **Architecture** — maps your directory tree and identifies frameworks
- **Commands** — finds your test runner, linter, formatter, build tool
- **Anti-patterns** — flags what NOT to do based on your stack
- **Domain context** — extracts your key classes, API endpoints, enums

## Try It

1. Go to [anchormd.dev](https://anchormd.dev)
2. Paste a GitHub URL
3. Get a CLAUDE.md in 30 seconds

Sign in with GitHub to scan private repos or batch-scan your entire account.

CLI: `pip install anchormd && anchormd generate .`

The tool scores your context file 0-100 with specific recommendations. Most repos I've scanned start at 0 (no file) and jump to 75-95 after generation.

---

*anchormd is MIT licensed. Pro tier ($8/mo) adds interactive init, diff detection, and tech debt scanning. Deep scan reports ($29 one-time) coming soon.*
