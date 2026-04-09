---
name: anchormd-audit
description: Audit an existing CLAUDE.md file for quality, completeness, and accuracy. Use when reviewing a project's CLAUDE.md for staleness, when checking if a CLAUDE.md meets quality standards, when a CLAUDE.md might have drifted from the actual codebase, or when evaluating CLAUDE.md files across a fleet of repositories. Scores across 8 dimensions and reports specific issues with actionable fixes.
license: MIT
---

# Audit CLAUDE.md

Audit an existing CLAUDE.md for quality and completeness using anchormd.

## Prerequisites

anchormd must be installed: `pip install anchormd`

## Workflow

1. Run the audit against an existing CLAUDE.md:
   ```bash
   anchormd audit CLAUDE.md
   ```

2. Review the score breakdown. The audit checks 8 dimensions:
   - **Project overview** — Does it describe what the project is?
   - **Architecture** — Are key directories and patterns documented?
   - **Build commands** — Are build/test/lint commands listed?
   - **Coding standards** — Are style rules and conventions specified?
   - **Anti-patterns** — Are common mistakes documented?
   - **Dependencies** — Are key dependencies and versions noted?
   - **Testing** — Are test patterns and commands covered?
   - **Security** — Are security considerations documented?

3. Address reported issues. Each issue includes:
   - The dimension it affects
   - What's missing or incorrect
   - A suggested fix

4. Re-audit after fixes to confirm improvement:
   ```bash
   anchormd audit CLAUDE.md
   ```

## Scoring

- **90-100**: Excellent — comprehensive and current
- **70-89**: Good — covers essentials, minor gaps
- **50-69**: Adequate — usable but missing key sections
- **Below 50**: Needs work — significant gaps affect agent effectiveness

## Pro Features

With a Pro license, additional audit capabilities:
- `anchormd tech-debt` — Technical debt analysis
- `anchormd github-health` — Repository health scoring
- `anchormd cleanup` — Automated issue remediation
