# Prompt 06 — Auditor

## Context
You are building AnchorMD. Read CLAUDE.md for full context. Prompts 01-05 are complete — full pipeline and CLI working.

## Task
Build the auditor that evaluates existing CLAUDE.md files against best practices and the actual codebase state.

## Steps

### 1. Auditor (`src/anchormd/generators/auditor.py`)

```python
class ClaudeMdAuditor:
    """Audits an existing CLAUDE.md against the actual codebase and best practices."""

    def __init__(self, config: ForgeConfig): ...

    def audit(self, claude_md_content: str, structure: ProjectStructure, analyses: list[AnalysisResult]) -> AuditReport:
        """Full audit producing scored report with findings."""

    def _check_section_coverage(self, content: str) -> list[AuditFinding]:
        """Check which recommended sections are present/missing."""

    def _check_accuracy(self, content: str, structure: ProjectStructure, analyses: list[AnalysisResult]) -> list[AuditFinding]:
        """Compare CLAUDE.md claims against actual codebase state."""

    def _check_anti_patterns(self, content: str) -> list[AuditFinding]:
        """Check for common CLAUDE.md anti-patterns."""

    def _check_specificity(self, content: str) -> list[AuditFinding]:
        """Check for vague/generic content that should be specific."""

    def _check_freshness(self, content: str, structure: ProjectStructure) -> list[AuditFinding]:
        """Detect stale information (e.g., mentions removed deps)."""

    def _calculate_score(self, findings: list[AuditFinding], section_count: int) -> int:
        """Score 0-100 based on findings severity and coverage."""
```

### 2. Audit Rules

**Section Coverage** (errors for missing critical sections):
- `error`: Missing "Project Overview" or description
- `error`: Missing "Common Commands" (agents need to know how to run things)
- `error`: Missing "Architecture" or project structure
- `warning`: Missing "Coding Standards"
- `warning`: Missing "Anti-Patterns"
- `info`: Missing "Dependencies"
- `info`: Missing "Git Conventions"
- `info`: Missing "Domain Context"

**Accuracy Checks** (compare CLAUDE.md claims vs reality):
- `error`: Says "greenfield" but project has >50 source files
- `error`: Lists framework not found in dependencies
- `warning`: Lists commands that reference tools not in the project
- `warning`: Mentions test framework that doesn't match actual test files
- `warning`: Architecture tree doesn't match actual directory structure
- `info`: Version number in CLAUDE.md doesn't match pyproject.toml/package.json

**Anti-Pattern Detection in CLAUDE.md itself**:
- `warning`: CLAUDE.md is > 500 lines (too long, agents lose context)
- `warning`: CLAUDE.md is < 20 lines (too short, not enough context)
- `warning`: Contains TODO/FIXME items (stale planning artifacts)
- `warning`: Contains prompts or conversation fragments (copy-paste from AI chat)
- `info`: Uses first-person ("I want...", "We use...") instead of declarative style
- `info`: Contains markdown rendering issues (unclosed code blocks, broken links)

**Specificity Checks**:
- `warning`: Generic statements like "follow best practices" without specifics
- `warning`: "Use standard conventions" without defining which conventions
- `info`: Anti-patterns section lacks code examples
- `info`: Commands section lacks actual command strings

**Freshness Checks**:
- `warning`: References files/directories that don't exist in the project
- `warning`: References dependencies not found in config files
- `info`: CLAUDE.md file modification date is > 30 days older than most recent source change

### 3. Scoring Algorithm

```
base_score = 100
per_error = -15
per_warning = -5
per_info = -1

section_bonus = (sections_present / total_recommended_sections) * 20
specificity_bonus = (specific_items_found / total_checkable_items) * 10

final_score = clamp(base_score + deductions + section_bonus + specificity_bonus, 0, 100)
```

### 4. Tests (`tests/test_auditor.py`)

- Test: Perfect CLAUDE.md scores > 80
- Test: Empty CLAUDE.md scores < 20
- Test: Missing "Common Commands" produces error finding
- Test: "greenfield" in 100-file project produces error finding
- Test: CLAUDE.md > 500 lines produces warning
- Test: CLAUDE.md < 20 lines produces warning
- Test: Stale file references produce warning
- Test: Generic "follow best practices" produces warning
- Test: Score is always 0-100

## Acceptance Criteria
- `pytest tests/test_auditor.py -v` — all pass
- Running auditor on this project's own CLAUDE.md produces reasonable findings
- `anchormd audit CLAUDE.md` shows colored, actionable output
- Audit of a truly bad CLAUDE.md (just "# CLAUDE.md" with nothing else) scores < 20
- Audit of a well-crafted CLAUDE.md scores > 70
- `ruff check src/anchormd/generators/auditor.py` — clean
