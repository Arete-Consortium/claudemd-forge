# Changelog

All notable changes to anchormd are documented here. This project follows [Semantic Versioning](https://semver.org/).

## [0.5.0] - 2026-04-17

### Added
- `anchormd verify <CLAUDE.md>` — cross-checks claims against reality. Verifies file paths in architecture blocks, project version vs `pyproject.toml`/`package.json`, and dependencies vs the manifest. Complements `audit` (structure scoring) with a truth score.
- `anchormd fleet [root]` — walks a root directory for every `CLAUDE.md`, audits each in parallel, and emits a ranked report (lowest score first). Prunes heavy directories (`.venv`, `node_modules`, `.flatpak-builder`, etc.) during descent. Optional `--reality` for two-column scoring, `--min-score`, `--limit`, `--json`.
- `anchormd harvest [project]` — parses `~/.claude/projects/<slug>/*.jsonl` transcripts, extracts tool errors, normalizes them (strips paths/hex/numbers), and surfaces recurring gotchas by tool + signature. Reveals patterns like repeated Edit-before-Read failures or file-too-large Reads.
- `anchormd patch <CLAUDE.md>` — harvests gotchas and splices matching anti-patterns into the file's `## Anti-Patterns` section. Case-insensitive dedupe by bullet title, diff preview, `--dry-run` / `-y` flags.
- Gotcha → anti-pattern suggestion library (`analyzers/suggestions.py`) with rules for Edit/Write without Read, Read token-limit overflow, Edit on stale read, WebFetch status failures, `command not found`, `rm → trash` aliasing, and user-denied tool uses.
- `ANCHORMD_STRICT=1` — opt-in strict licensing mode that closes the fail-open path. Any validation failure (missing key, server unreachable with no cache, revoked or expired key) drops to Free and exits non-zero on Pro commands. Recommended for CI and unattended pipelines.
- `tech-debt --source-only` flag to restrict scanning to source directories, plus `--include-path` and `--exclude` filters for finer control over which files are audited.

### Changed
- Version bumped 0.4.1 → 0.5.0.
- CLAUDE.md updated to reflect the new command set and correct the `api/core/generator.py` → `web/generator.py` path.

### Infrastructure
- 19 new tests across `test_reality.py`, `test_harvest.py`, `test_suggestions.py`, `test_patcher.py`. Full suite: 374 passing.
