# AnchorMD — Build Execution Guide

## How to Use These Prompts

Each prompt in `/prompts/` is designed to be fed to Claude Code as a single session.
Run them **in order** — each builds on the previous.

### Setup

```bash
# Create repo
mkdir anchormd && cd anchormd
git init

# Copy this entire scaffold into the repo
# (CLAUDE.md, prompts/, docs/ should all be at root)

git add -A
git commit -m "feat: initial scaffold with CLAUDE.md and build prompts"
```

### Execution Sequence

| Prompt | Time Estimate | What It Builds | Commit After |
|--------|---------------|----------------|--------------|
| 01_foundation | 15-20 min | pyproject.toml, models, config, exceptions | `feat: project foundation and data models` |
| 02_scanner | 20-30 min | Filesystem scanner with tests | `feat: codebase scanner` |
| 03_analyzers | 30-45 min | 4 analyzers (language, patterns, commands, domain) | `feat: codebase analyzers` |
| 04_generators | 20-30 min | Section generator + document composer | `feat: CLAUDE.md generators` |
| 05_cli | 20-30 min | Typer CLI with rich output | `feat: CLI interface` |
| 06_auditor | 20-30 min | CLAUDE.md quality auditor | `feat: audit command` |
| 07_templates | 30-40 min | Framework presets + Jinja2 templates | `feat: framework presets and templates` |
| 08_publish | 15-20 min | README, CI/CD, PyPI prep | `feat: publish pipeline` |

**Total estimated: 3-4 hours of Claude Code sessions**

### Per-Prompt Workflow

```bash
# 1. Open Claude Code in the project root
cd anchormd
claude

# 2. Feed the prompt
# Copy contents of prompts/01_foundation.md into Claude Code

# 3. Let it build. Review output.

# 4. Run tests
pytest tests/ -v

# 5. Run lint
ruff check src/ tests/

# 6. If tests pass, commit
git add -A
git commit -m "feat: project foundation and data models"

# 7. Move to next prompt
```

### Tips

- **Always run tests before committing.** If tests fail, paste the failure into Claude Code and ask it to fix.
- **Dogfood early.** After prompt 05, run `anchormd generate .` on the project itself. Fix issues immediately.
- **Don't skip the auditor.** Prompt 06 is what makes this tool premium — it's the reason someone would pay for it.
- **The templates in prompt 07 are your monetization lever.** Curated, opinionated presets are the value-add over hand-rolling.

### Post-Build Checklist

- [ ] `anchormd generate .` works on itself
- [ ] `anchormd audit CLAUDE.md` scores > 60 on its own CLAUDE.md
- [ ] `anchormd generate /path/to/some/react/project` produces good output
- [ ] `anchormd generate /path/to/some/python/project` produces good output
- [ ] All tests pass across Python 3.11+
- [ ] Published to PyPI
- [ ] GitHub repo has: pinned, README with badges, release tagged

### Monetization Next Steps (After v0.1.0 ships)

1. **Free CLI on PyPI** — builds adoption, gets stars
2. **Gumroad template packs** ($5-10 each): "Enterprise Python", "Full-Stack TypeScript", "Rust Systems"
3. **GitHub Action** (free tier + paid): auto-audit on PR, comment with score
4. **Pro CLI** ($5/mo via license key): team templates, custom rules, CI integration
5. **Landing page**: benchmarks showing quality improvement with Forge-generated CLAUDE.md vs hand-written
