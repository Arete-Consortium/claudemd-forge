# r/cursor Post Draft

**Title:** Free tool to generate context files (CLAUDE.md / .cursorrules) for any repo — scans your actual code patterns

**Body:**

Context files make a massive difference in AI code assistants. Whether you use Cursor, Claude Code, or Copilot, giving the AI accurate project context means fewer hallucinations and better suggestions.

I built **anchormd** to automate this. It scans your codebase and generates a complete context file with:

- Detected coding standards (naming, quotes, imports — from your actual code, not guesses)
- Architecture tree
- Common commands (auto-detects your test/lint/build setup)
- Anti-patterns specific to your stack
- Key models, API endpoints, domain terms
- Quality score (0-100) with a downloadable fix report showing exactly how to reach 100

**Try it:** [anchormd.dev](https://anchormd.dev) — paste any public GitHub URL. Sign in with GitHub for private repos and batch-scan your entire account.

**CLI:** `pip install anchormd && anchormd generate .`

One-click export to the native format for each agent: `CLAUDE.md`, `.cursorrules`, `.github/copilot-instructions.md`, and `.windsurfrules`. Or push a PR to your repo directly.

~700 tests. Licensed under BSL-1.1 (with an MIT change date). Feedback welcome.
