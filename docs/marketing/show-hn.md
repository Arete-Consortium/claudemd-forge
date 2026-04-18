# Show HN Post Draft

**Title:** Show HN: Anchormd – Generate AI coding agent context files from any GitHub repo

**URL:** https://anchormd.dev

**Body:**

Anchormd reads a GitHub repo and writes the context file your AI coding agent needs — `CLAUDE.md` for Claude Code, `.cursorrules` for Cursor, `.github/copilot-instructions.md` for Copilot, or `.windsurfrules` for Windsurf. Paste a URL, pick a format, download.

The problem I kept running into: the agent's only as good as the context file, and the context file is the thing nobody wants to write. Templates go stale. Hand-written ones drift from reality within weeks. And if you switch agents you start over.

Anchormd runs 8 analyzers over your actual code — naming conventions, import style, quote style, directory layout, detected test/lint/build commands, domain terms pulled from class names and API routes — and scores the output 0-100 against a quality rubric (coverage, specificity, freshness). Score under 100? Download a fix report with gap analysis, copy-paste templates for missing sections, and a one-shot prompt that closes the gaps.

It's the audit, not the generator, that I think is novel. A half-written CLAUDE.md is worse than none — the agent confidently follows stale rules. The scorer catches that.

**Try it:** paste any public GitHub URL at https://anchormd.dev (no signup, ~30 seconds). Sign in with GitHub to batch-scan every repo you own.

**CLI:** `pip install anchormd && anchormd generate .`

MIT licensed CLI, ~700 tests. Pro tier ($8/mo) adds interactive `init`, `diff` (drift detection), and `tech-debt` scanning. One-time $29 deep-scan report for a full architectural audit.

Source: https://github.com/Arete-Consortium/anchormd

Happy to answer questions about the analyzer design, scoring rubric, or the engineering tradeoffs in running untrusted repos as a public scanner.
