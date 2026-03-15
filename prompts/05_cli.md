# Prompt 05 — CLI Interface

## Context
You are building AnchorMD. Read CLAUDE.md for full context. Prompts 01-04 are complete — models, scanner, analyzers, and generators all exist and pass tests.

## Task
Build the CLI interface using Typer with rich terminal output.

## Steps

### 1. CLI Entrypoint (`src/anchormd/cli.py`)

```python
import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress

app = typer.Typer(
    name="anchormd",
    help="Generate and audit CLAUDE.md files for AI coding agents.",
    no_args_is_help=True,
)
console = Console()

@app.command()
def generate(
    path: Path = typer.Argument(".", help="Path to project root"),
    output: Path | None = typer.Option(None, "-o", "--output", help="Output file path (default: ./CLAUDE.md)"),
    preset: str = typer.Option("default", "-p", "--preset", help="Template preset"),
    force: bool = typer.Option(False, "-f", "--force", help="Overwrite existing CLAUDE.md"),
    quiet: bool = typer.Option(False, "-q", "--quiet", help="Suppress progress output"),
) -> None:
    """Generate a CLAUDE.md file for the target project."""
    # 1. Validate path exists and is a directory
    # 2. Check if CLAUDE.md exists (warn if not --force)
    # 3. Show scanning progress with rich Progress bar
    # 4. Run scanner
    # 5. Run all analyzers (show progress per analyzer)
    # 6. Run composer
    # 7. Write output file
    # 8. Show quality score and summary panel

@app.command()
def audit(
    path: Path = typer.Argument(..., help="Path to existing CLAUDE.md file"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Show detailed findings"),
) -> None:
    """Audit an existing CLAUDE.md file for gaps and improvements."""
    # 1. Read existing CLAUDE.md
    # 2. Also scan the project directory (parent of CLAUDE.md)
    # 3. Run auditor
    # 4. Display findings with severity colors (red/yellow/blue)
    # 5. Display score with visual bar
    # 6. Show actionable recommendations

@app.command()
def init(
    path: Path = typer.Argument(".", help="Path to project root"),
    interactive: bool = typer.Option(True, "--no-interactive", help="Disable interactive prompts"),
) -> None:
    """Initialize a CLAUDE.md with interactive prompts."""
    # 1. Scan project
    # 2. Show detected stack, ask user to confirm/correct
    # 3. Ask for project description
    # 4. Ask for any domain-specific terms to include
    # 5. Generate with user input merged
    # 6. Write file

@app.command()
def diff(
    path: Path = typer.Argument(".", help="Path to project root"),
) -> None:
    """Show what would change if CLAUDE.md were regenerated."""
    # 1. Read existing CLAUDE.md
    # 2. Generate fresh one
    # 3. Show unified diff with rich syntax highlighting

@app.command()
def presets(
) -> None:
    """List available template presets."""
    # Display table of presets with descriptions
```

### 2. Output Formatting

Use rich for all terminal output:
- **Scanning**: Progress bar with file count
- **Analysis**: Spinner per analyzer with name
- **Results**: Panel showing quality score, sections generated, file written
- **Audit**: Table of findings with colored severity
- **Errors**: Red panels with actionable messages

Example output:
```
╭─ AnchorMD ─────────────────────────────────╮
│                                                    │
│  📁 Scanned: 247 files across 12 languages        │
│  🔍 Analyzed: tech stack, patterns, commands       │
│  📝 Generated: CLAUDE.md (142 lines)               │
│  ⭐ Quality Score: 78/100                          │
│                                                    │
│  Sections: Project Overview, Architecture,         │
│  Tech Stack, Coding Standards, Common Commands,    │
│  Anti-Patterns, Dependencies, Git Conventions      │
│                                                    │
╰───────────────────────────────────────────────────╯
```

### 3. Tests (`tests/test_cli.py`)

Use `typer.testing.CliRunner`:
- Test: `generate .` on a temp project produces a CLAUDE.md file
- Test: `generate` without `--force` refuses to overwrite existing CLAUDE.md
- Test: `generate --force` overwrites existing CLAUDE.md
- Test: `generate --quiet` suppresses progress output
- Test: `audit` on a minimal CLAUDE.md reports missing sections
- Test: `presets` lists available presets
- Test: Invalid path shows error message
- Test: `--help` shows usage info for each command

## Acceptance Criteria
- `python -m anchormd generate .` works on the anchormd project itself
- `python -m anchormd audit CLAUDE.md` produces findings
- All CLI tests pass
- Exit codes: 0 for success, 1 for error, 2 for warnings-only
- No tracebacks shown to user — all exceptions caught and displayed as rich panels
- `ruff check src/anchormd/cli.py` — clean
