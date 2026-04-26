"""CLI entrypoint for AnchorMD."""

from __future__ import annotations

import difflib
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from anchormd import __version__
from anchormd.analyzers import run_all
from anchormd.exceptions import ForgeError
from anchormd.gates import check_preset_access, record_scan_usage, require_pro, require_quota
from anchormd.generators.composer import DocumentComposer
from anchormd.licensing import (
    PRO_PRESETS,
    TIER_DEFINITIONS,
    Tier,
    get_license_info,
)
from anchormd.models import ForgeConfig
from anchormd.scanner import CodebaseScanner
from anchormd.telemetry import track_command

_DEFAULT_FLEET_ROOT = Path.home() / "projects"

app = typer.Typer(
    name="anchormd",
    help="Generate and audit CLAUDE.md files for AI coding agents.",
    no_args_is_help=True,
)
console = Console()

# Register drift sub-command group.
from anchormd.drift.cli import drift_app  # noqa: E402

app.add_typer(drift_app, name="drift", help="Agent behavioral drift detection.")


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"anchormd {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(  # noqa: B008
        False, "--version", "-V", help="Show version", callback=_version_callback, is_eager=True
    ),
) -> None:
    """AnchorMD — Generate and audit CLAUDE.md files for AI coding agents."""


def _inject_overview_description(content: str, description: str) -> str:
    """Replace the first project overview paragraph with a user-provided description."""
    if not description:
        return content

    pattern = re.compile(r"(## Project Overview\n\n)(.*?)(\n\n)", re.DOTALL)
    match = pattern.search(content)
    if not match:
        return content
    return pattern.sub(lambda m: f"{m.group(1)}{description}{m.group(3)}", content, count=1)


@app.command()
def generate(
    path: Path = typer.Argument(  # noqa: B008
        Path("."), help="Path to project root"
    ),
    output: Path | None = typer.Option(  # noqa: B008
        None, "-o", "--output", help="Output file path"
    ),
    preset: str = typer.Option(  # noqa: B008
        "default", "-p", "--preset", help="Template preset"
    ),
    force: bool = typer.Option(  # noqa: B008
        False, "-f", "--force", help="Overwrite existing CLAUDE.md"
    ),
    quiet: bool = typer.Option(  # noqa: B008
        False, "-q", "--quiet", help="Suppress progress output"
    ),
) -> None:
    """Generate a CLAUDE.md file for the target project."""
    track_command("generate")
    try:
        root = path.resolve()
        if not root.is_dir():
            console.print(f"[red]Error:[/red] {root} is not a directory.")
            raise typer.Exit(1)

        # Check preset access before doing any work.
        check_preset_access(preset)

        out_path = output or (root / "CLAUDE.md")
        if out_path.exists() and not force:
            console.print(
                f"[yellow]Warning:[/yellow] {out_path} already exists. Use --force to overwrite."
            )
            raise typer.Exit(1)

        config = ForgeConfig(root_path=root, output_path=out_path, preset=preset)

        if not quiet:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Scanning codebase...", total=None)
                scanner = CodebaseScanner(config)
                structure = scanner.scan()
                progress.update(task, description=f"Scanned {structure.total_files} files")

                task = progress.add_task("Running analyzers...", total=None)
                analyses = run_all(structure, config)
                progress.update(task, description=f"Analyzed {len(analyses)} dimensions")

                task = progress.add_task("Composing CLAUDE.md...", total=None)
                composer = DocumentComposer(config)
                content = composer.compose(structure, analyses)
                score = composer.estimate_quality_score(content)
                progress.update(task, description="Done")
        else:
            scanner = CodebaseScanner(config)
            structure = scanner.scan()
            analyses = run_all(structure, config)
            composer = DocumentComposer(config)
            content = composer.compose(structure, analyses)

        out_path.write_text(content)

        if not quiet:
            line_count = len(content.splitlines())
            sections = [
                line.lstrip("# ").strip() for line in content.splitlines() if line.startswith("## ")
            ]
            console.print()
            console.print(
                Panel(
                    f"  Scanned: {structure.total_files} files across "
                    f"{len(structure.languages)} languages\n"
                    f"  Generated: {out_path.name} ({line_count} lines)\n"
                    f"  Quality Score: {score}/100\n\n"
                    f"  Sections: {', '.join(sections)}",
                    title="AnchorMD",
                    border_style="green",
                )
            )

    except ForgeError as e:
        console.print(Panel(str(e), title="Error", border_style="red"))
        raise typer.Exit(1) from e


@app.command()
def audit(
    path: Path = typer.Argument(  # noqa: B008
        ..., help="Path to existing CLAUDE.md file"
    ),
    verbose: bool = typer.Option(  # noqa: B008
        False, "-v", "--verbose", help="Show detailed findings"
    ),
    output_json: bool = typer.Option(  # noqa: B008
        False, "--json", help="Output results as JSON"
    ),
    fail_below: int = typer.Option(  # noqa: B008
        40, "--fail-below", help="Exit with code 2 if score is below this threshold"
    ),
) -> None:
    """Audit an existing CLAUDE.md file for gaps and improvements."""
    track_command("audit")
    try:
        target = path.resolve()
        if not target.is_file():
            if output_json:
                print(json.dumps({"error": f"{target} is not a file"}))  # noqa: T201
            else:
                console.print(f"[red]Error:[/red] {target} is not a file.")
            raise typer.Exit(1)

        claude_content = target.read_text()
        project_root = target.parent

        config = ForgeConfig(root_path=project_root)
        scanner = CodebaseScanner(config)
        structure = scanner.scan()
        analyses = run_all(structure, config)

        # Lazy import to avoid circular.
        from anchormd.generators.auditor import ClaudeMdAuditor

        auditor = ClaudeMdAuditor(config)
        report = auditor.audit(claude_content, structure, analyses)

        if output_json:
            print(  # noqa: T201
                json.dumps(
                    {
                        "score": report.score,
                        "findings": [f.model_dump() for f in report.findings],
                        "missing_sections": report.missing_sections,
                        "recommendations": report.recommendations,
                    },
                    indent=2,
                )
            )
        else:
            # Display findings.
            if report.findings:
                table = Table(title="Audit Findings")
                table.add_column("Severity", style="bold")
                table.add_column("Category")
                table.add_column("Message")

                severity_styles = {"error": "red", "warning": "yellow", "info": "blue"}

                for finding in report.findings:
                    style = severity_styles.get(finding.severity, "white")
                    table.add_row(
                        f"[{style}]{finding.severity.upper()}[/{style}]",
                        finding.category,
                        finding.message,
                    )
                    if verbose and finding.suggestion:
                        table.add_row("", "", f"  -> {finding.suggestion}")

                console.print(table)

            if report.missing_sections:
                missing = ", ".join(report.missing_sections)
                console.print(f"\n[yellow]Missing sections:[/yellow] {missing}")

            # Score display.
            score_color = (
                "green" if report.score >= 70 else "yellow" if report.score >= 40 else "red"
            )
            console.print(f"\n[{score_color}]Score: {report.score}/100[/{score_color}]")

            if report.recommendations:
                console.print("\n[bold]Recommendations:[/bold]")
                for rec in report.recommendations:
                    console.print(f"  - {rec}")

        if report.score < fail_below:
            raise typer.Exit(2)

    except ForgeError as e:
        if output_json:
            print(json.dumps({"error": str(e)}))  # noqa: T201
        else:
            console.print(Panel(str(e), title="Error", border_style="red"))
        raise typer.Exit(1) from e


@app.command()
def verify(
    path: Path = typer.Argument(  # noqa: B008
        ..., help="Path to existing CLAUDE.md file"
    ),
    output_json: bool = typer.Option(  # noqa: B008
        False, "--json", help="Output results as JSON"
    ),
    fail_below: int = typer.Option(  # noqa: B008
        80, "--fail-below", help="Exit code 2 if reality score below this threshold"
    ),
) -> None:
    """Verify CLAUDE.md claims against the filesystem (files, version, deps)."""
    track_command("verify")
    from anchormd.analyzers.reality import verify as run_verify

    target = path.resolve()
    if not target.is_file():
        msg = f"{target} is not a file"
        if output_json:
            print(json.dumps({"error": msg}))  # noqa: T201
        else:
            console.print(f"[red]Error:[/red] {msg}.")
        raise typer.Exit(1)

    report = run_verify(target.read_text(), target.parent)

    if output_json:
        print(  # noqa: T201
            json.dumps(
                {
                    "score": report.score,
                    "checks_run": report.checks_run,
                    "checks_passed": report.checks_passed,
                    "findings": [
                        {
                            "severity": f.severity,
                            "category": f.category,
                            "message": f.message,
                            "claim": f.claim,
                            "suggestion": f.suggestion,
                        }
                        for f in report.findings
                    ],
                },
                indent=2,
            )
        )
    else:
        if report.findings:
            table = Table(title="Reality Check Findings")
            table.add_column("Severity", style="bold")
            table.add_column("Category")
            table.add_column("Claim")
            table.add_column("Message")
            severity_styles = {"error": "red", "warning": "yellow", "info": "blue"}
            for f in report.findings:
                style = severity_styles.get(f.severity, "white")
                table.add_row(
                    f"[{style}]{f.severity.upper()}[/{style}]",
                    f.category,
                    f.claim[:50],
                    f.message,
                )
            console.print(table)
        else:
            console.print("[green]All claims verified.[/green]")

        score_color = "green" if report.score >= 90 else "yellow" if report.score >= 70 else "red"
        console.print(
            f"\n[{score_color}]Reality score: {report.score}/100 "
            f"({report.checks_passed}/{report.checks_run} checks passed)[/{score_color}]"
        )

    if report.score < fail_below and report.checks_run > 0:
        raise typer.Exit(2)


@app.command()
def fleet(
    root: Path = typer.Argument(  # noqa: B008
        _DEFAULT_FLEET_ROOT, help="Root directory to scan for CLAUDE.md files"
    ),
    output_json: bool = typer.Option(  # noqa: B008
        False, "--json", help="Output results as JSON"
    ),
    min_score: int = typer.Option(  # noqa: B008
        0, "--min-score", help="Only include projects scoring at or above this"
    ),
    reality: bool = typer.Option(  # noqa: B008
        False, "--reality", help="Also run reality verification (slower)"
    ),
    limit: int = typer.Option(  # noqa: B008
        0, "--limit", help="Only show top N projects (0 = show all)"
    ),
) -> None:
    """Audit every CLAUDE.md under a root directory and emit a ranked report."""
    track_command("fleet")
    from anchormd.analyzers.reality import verify as run_verify
    from anchormd.generators.auditor import ClaudeMdAuditor

    root = root.resolve()
    if not root.is_dir():
        msg = f"{root} is not a directory"
        if output_json:
            print(json.dumps({"error": msg}))  # noqa: T201
        else:
            console.print(f"[red]Error:[/red] {msg}.")
        raise typer.Exit(1)

    # Find CLAUDE.md files, pruning heavy/forbidden directories during descent.
    import os as _os

    claude_files: list[Path] = []
    skip_parts = {
        ".venv",
        "venv",
        "node_modules",
        ".git",
        "__pycache__",
        "dist",
        "build",
        ".next",
        "target",
        ".flatpak-builder",
        ".cache",
        ".tox",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".animus",
        "site-packages",
    }
    for dirpath, dirnames, filenames in _os.walk(root, topdown=True, followlinks=False):
        # Prune subdirs in-place.
        dirnames[:] = [d for d in dirnames if d not in skip_parts and not d.startswith(".")]
        if "CLAUDE.md" in filenames:
            candidate = Path(dirpath) / "CLAUDE.md"
            try:
                rel = candidate.relative_to(root)
            except ValueError:
                continue
            # Keep project-root CLAUDE.md only (one level deep from root).
            if len(rel.parts) > 2:
                continue
            claude_files.append(candidate)

    import contextlib
    import io

    def _audit_one(claude_path: Path) -> dict[str, Any]:
        project_root = claude_path.parent
        project_name = project_root.name
        try:
            content = claude_path.read_text()
            config = ForgeConfig(root_path=project_root)
            # Silence scanner/analyzer stderr noise (permission denied etc).
            with contextlib.redirect_stderr(io.StringIO()):
                scanner = CodebaseScanner(config)
                structure = scanner.scan()
                analyses = run_all(structure, config)
            auditor = ClaudeMdAuditor(config)
            audit_report = auditor.audit(content, structure, analyses)
            entry = {
                "project": project_name,
                "path": str(claude_path),
                "audit_score": audit_report.score,
                "missing_sections": audit_report.missing_sections,
            }
            if reality:
                reality_report = run_verify(content, project_root)
                entry["reality_score"] = reality_report.score
                entry["reality_findings"] = len(reality_report.findings)
            return entry
        except Exception as exc:  # noqa: BLE001
            return {
                "project": project_name,
                "path": str(claude_path),
                "audit_score": 0,
                "error": str(exc),
            }

    console.print(f"[dim]Auditing {len(claude_files)} project(s)...[/dim]")
    results: list[dict[str, Any]] = []
    from concurrent.futures import ThreadPoolExecutor, as_completed

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(_audit_one, cp): cp for cp in claude_files}
        for i, fut in enumerate(as_completed(futures), 1):
            results.append(fut.result())
            if i % 10 == 0:
                console.print(f"[dim]  {i}/{len(claude_files)}[/dim]")

    # Sort ascending by audit_score — worst first (highest ROI to fix).
    results.sort(key=lambda r: r.get("audit_score", 0))
    filtered = [r for r in results if r.get("audit_score", 0) >= min_score]
    if limit > 0:
        filtered = filtered[:limit]

    if output_json:
        print(json.dumps({"root": str(root), "total": len(results), "results": filtered}, indent=2))  # noqa: T201
        return

    if not filtered:
        console.print(f"[yellow]No CLAUDE.md files found under {root}[/yellow]")
        return

    table = Table(title=f"Fleet Audit ({len(filtered)}/{len(results)} shown)")
    table.add_column("Project", style="bold")
    table.add_column("Audit", justify="right")
    if reality:
        table.add_column("Reality", justify="right")
    table.add_column("Missing Sections")
    for r in filtered:
        audit = r.get("audit_score", 0)
        audit_color = "green" if audit >= 70 else "yellow" if audit >= 40 else "red"
        row = [
            r["project"],
            f"[{audit_color}]{audit}[/{audit_color}]",
        ]
        if reality:
            rs = r.get("reality_score", "—")
            if isinstance(rs, int):
                rs_color = "green" if rs >= 90 else "yellow" if rs >= 70 else "red"
                row.append(f"[{rs_color}]{rs}[/{rs_color}]")
            else:
                row.append("—")
        row.append(", ".join(r.get("missing_sections", []))[:60])
        table.add_row(*row)
    console.print(table)

    # Summary stats.
    avg = sum(r.get("audit_score", 0) for r in results) / max(len(results), 1)
    below_70 = sum(1 for r in results if r.get("audit_score", 0) < 70)
    console.print(
        f"\n[bold]Summary:[/bold] {len(results)} projects · "
        f"avg score {avg:.0f}/100 · {below_70} below 70"
    )


@app.command()
def harvest(
    path: Path = typer.Argument(Path("."), help="Project directory"),  # noqa: B008
    output_json: bool = typer.Option(  # noqa: B008
        False, "--json", help="Output results as JSON"
    ),
    min_count: int = typer.Option(  # noqa: B008
        2, "--min-count", help="Minimum recurrence count to surface"
    ),
    limit: int = typer.Option(  # noqa: B008
        10, "--limit", help="Top N gotchas to return"
    ),
    suggest: bool = typer.Option(  # noqa: B008
        False, "--suggest", help="Emit an Anti-Patterns markdown block ready for CLAUDE.md"
    ),
) -> None:
    """Harvest recurring tool errors from Claude Code transcripts for this project."""
    track_command("harvest")
    from anchormd.analyzers.harvest import harvest as run_harvest
    from anchormd.analyzers.suggestions import format_anti_patterns_block

    project_root = path.resolve()
    if not project_root.is_dir():
        msg = f"{project_root} is not a directory"
        if output_json:
            print(json.dumps({"error": msg}))  # noqa: T201
        else:
            console.print(f"[red]Error:[/red] {msg}.")
        raise typer.Exit(1)

    report = run_harvest(project_root, min_count=min_count, limit=limit)
    matched_suggestions = [g.suggestion for g in report.gotchas if g.suggestion]

    if output_json:
        print(  # noqa: T201
            json.dumps(
                {
                    "project": str(report.project_path),
                    "transcript_dir": str(report.transcript_dir) if report.transcript_dir else None,
                    "sessions_scanned": report.sessions_scanned,
                    "tool_errors": report.tool_errors,
                    "gotchas": [
                        {
                            "tool": g.tool,
                            "count": g.count,
                            "sessions": g.sessions,
                            "signature": g.signature,
                            "examples": g.examples,
                            "suggestion": (
                                {"title": g.suggestion.title, "body": g.suggestion.body}
                                if g.suggestion
                                else None
                            ),
                        }
                        for g in report.gotchas
                    ],
                    "suggestions_markdown": format_anti_patterns_block(matched_suggestions),
                },
                indent=2,
            )
        )
        return

    if report.transcript_dir is None:
        console.print(
            f"[yellow]No Claude Code transcripts found for {project_root}[/yellow]\n"
            f"Expected: ~/.claude/projects/<slug>/ matching this path."
        )
        return

    # --suggest: emit only the markdown block (for piping into CLAUDE.md edits).
    if suggest:
        block = format_anti_patterns_block(matched_suggestions)
        if block:
            print(block)  # noqa: T201
        else:
            console.print(
                "[yellow]No mapped suggestions — run without --suggest to see raw gotchas.[/yellow]"
            )
        return

    console.print(
        f"[dim]Transcripts: {report.transcript_dir} "
        f"({report.sessions_scanned} sessions, {report.tool_errors} errors)[/dim]"
    )

    if not report.gotchas:
        console.print(f"[green]No recurring gotchas (min_count={min_count}).[/green]")
        return

    table = Table(title=f"Top {len(report.gotchas)} recurring gotchas")
    table.add_column("#", justify="right", style="bold")
    table.add_column("Tool")
    table.add_column("Count", justify="right")
    table.add_column("Sessions", justify="right")
    table.add_column("Signature")
    table.add_column("Suggested Anti-Pattern")
    for i, g in enumerate(report.gotchas, 1):
        suggestion_text = g.suggestion.title if g.suggestion else "[dim]—[/dim]"
        table.add_row(
            str(i),
            g.tool,
            str(g.count),
            str(g.sessions),
            g.signature[:50],
            suggestion_text,
        )
    console.print(table)

    mapped = len(matched_suggestions)
    if mapped:
        total = len(report.gotchas)
        console.print(
            f"\n[green]{mapped}/{total} gotchas have known anti-pattern mappings.[/green]"
        )
        console.print(
            "Re-run with [bold]--suggest[/bold] to emit a markdown block ready for CLAUDE.md."
        )
    else:
        console.print(
            "\n[yellow]No known anti-pattern mappings matched. "
            "Convert gotchas into CLAUDE.md anti-patterns manually.[/yellow]"
        )


@app.command()
def patch(
    path: Path = typer.Argument(  # noqa: B008
        ..., help="Path to existing CLAUDE.md file"
    ),
    dry_run: bool = typer.Option(  # noqa: B008
        False, "-n", "--dry-run", help="Show the diff but don't write"
    ),
    yes: bool = typer.Option(  # noqa: B008
        False, "-y", "--yes", help="Skip confirmation"
    ),
    min_count: int = typer.Option(  # noqa: B008
        2, "--min-count", help="Minimum gotcha recurrence to harvest"
    ),
    limit: int = typer.Option(  # noqa: B008
        20, "--limit", help="Max gotchas to consider for suggestions"
    ),
) -> None:
    """Harvest gotchas and splice new anti-patterns into CLAUDE.md."""
    track_command("patch")
    from anchormd.analyzers.harvest import harvest as run_harvest
    from anchormd.analyzers.suggestions import format_bullets
    from anchormd.generators.patcher import patch as run_patch

    target = path.resolve()
    if not target.is_file():
        console.print(f"[red]Error:[/red] {target} is not a file.")
        raise typer.Exit(1)

    project_root = target.parent
    report = run_harvest(project_root, min_count=min_count, limit=limit)

    if report.transcript_dir is None:
        console.print(f"[yellow]No Claude Code transcripts found for {project_root}.[/yellow]")
        raise typer.Exit(0)

    suggestions = [g.suggestion for g in report.gotchas if g.suggestion]
    if not suggestions:
        console.print(
            f"[yellow]No mapped anti-pattern suggestions from {report.tool_errors} errors.[/yellow]"
        )
        raise typer.Exit(0)

    bullets = format_bullets(suggestions)
    content = target.read_text()
    result = run_patch(content, bullets)

    if not result.changed:
        console.print(
            f"[green]All {result.skipped} suggested anti-patterns are already in "
            "CLAUDE.md. Nothing to add.[/green]"
        )
        raise typer.Exit(0)

    console.print(
        f"[bold]Adding:[/bold] {result.added} new bullet(s) · "
        f"[dim]skipping {result.skipped} already present[/dim]"
    )
    console.print(Panel(result.diff, title="Diff", border_style="cyan"))

    if dry_run:
        raise typer.Exit(0)

    if not yes:
        confirm = typer.confirm(f"Write these changes to {target}?", default=True)
        if not confirm:
            console.print("[yellow]Aborted.[/yellow]")
            raise typer.Exit(0)

    target.write_text(result.patched)
    console.print(f"[green]Patched:[/green] {target}")


@app.command()
@require_pro("init_interactive")
def init(
    path: Path = typer.Argument(Path("."), help="Path to project root"),  # noqa: B008
) -> None:
    """Initialize a CLAUDE.md with interactive prompts. [Pro]"""
    track_command("init")
    try:
        root = path.resolve()
        if not root.is_dir():
            console.print(f"[red]Error:[/red] {root} is not a directory.")
            raise typer.Exit(1)

        config = ForgeConfig(root_path=root)
        scanner = CodebaseScanner(config)
        structure = scanner.scan()
        analyses = run_all(structure, config)

        console.print(f"\nDetected: [bold]{structure.primary_language or 'Unknown'}[/bold] project")
        console.print(f"Files: {structure.total_files}, Lines: {structure.total_lines:,}")

        description = typer.prompt("Project description", default="")

        composer = DocumentComposer(config)
        content = composer.compose(structure, analyses, project_name=root.name)

        # Inject user description if provided.
        if description:
            content = _inject_overview_description(content, description)

        out_path = root / "CLAUDE.md"
        out_path.write_text(content)
        console.print(f"\n[green]Created {out_path}[/green]")

    except ForgeError as e:
        console.print(Panel(str(e), title="Error", border_style="red"))
        raise typer.Exit(1) from e


@app.command()
@require_pro("diff")
def diff(
    path: Path = typer.Argument(Path("."), help="Path to project root"),  # noqa: B008
) -> None:
    """Show what would change if CLAUDE.md were regenerated. [Pro]"""
    track_command("diff")
    try:
        root = path.resolve()
        existing_path = root / "CLAUDE.md"

        if not existing_path.is_file():
            console.print("[red]Error:[/red] No existing CLAUDE.md found.")
            raise typer.Exit(1)

        existing = existing_path.read_text()

        config = ForgeConfig(root_path=root)
        scanner = CodebaseScanner(config)
        structure = scanner.scan()
        analyses = run_all(structure, config)
        composer = DocumentComposer(config)
        generated = composer.compose(structure, analyses)

        diff_lines = list(
            difflib.unified_diff(
                existing.splitlines(keepends=True),
                generated.splitlines(keepends=True),
                fromfile="current CLAUDE.md",
                tofile="generated CLAUDE.md",
            )
        )

        if not diff_lines:
            console.print("[green]No changes — CLAUDE.md is up to date.[/green]")
        else:
            for line in diff_lines:
                if line.startswith("+"):
                    console.print(f"[green]{line.rstrip()}[/green]")
                elif line.startswith("-"):
                    console.print(f"[red]{line.rstrip()}[/red]")
                elif line.startswith("@@"):
                    console.print(f"[cyan]{line.rstrip()}[/cyan]")
                else:
                    console.print(line.rstrip())

    except ForgeError as e:
        console.print(Panel(str(e), title="Error", border_style="red"))
        raise typer.Exit(1) from e


@app.command()
def presets() -> None:
    """List available template presets."""
    track_command("presets")
    from anchormd.templates.presets import PRESET_PACKS

    info = get_license_info()
    table = Table(title="Available Presets")
    table.add_column("Name", style="bold")
    table.add_column("Description")
    table.add_column("Tier")
    table.add_column("Auto-detect")

    for name, pack in PRESET_PACKS.items():
        if name in PRO_PRESETS:
            tier_label = (
                "[green]Unlocked[/green]" if info.tier == Tier.PRO else "[yellow]Pro[/yellow]"
            )
        else:
            tier_label = "[dim]Free[/dim]"
        table.add_row(
            name,
            pack.description,
            tier_label,
            "Yes" if pack.auto_detect else "No",
        )

    console.print(table)

    if info.tier == Tier.FREE:
        console.print("\n[dim]Upgrade to Pro for premium presets: https://anchormd.dev/pro[/dim]")


@app.command()
def frameworks() -> None:
    """List available framework presets."""
    track_command("frameworks")
    from anchormd.templates.frameworks import (
        FRAMEWORK_PRESETS,
        PREMIUM_PRESETS,
    )

    info = get_license_info()

    table = Table(title="Framework Presets")
    table.add_column("Preset", style="bold")
    table.add_column("Description")
    table.add_column("Tier")
    table.add_column("Standards")
    table.add_column("Anti-patterns")

    # Community presets (free).
    for name, preset in FRAMEWORK_PRESETS.items():
        table.add_row(
            name,
            preset.description,
            "[dim]Free[/dim]",
            str(len(preset.coding_standards)),
            str(len(preset.anti_patterns)),
        )

    # Premium presets.
    for name, preset in PREMIUM_PRESETS.items():
        tier_label = "[green]Unlocked[/green]" if info.tier == Tier.PRO else "[yellow]Pro[/yellow]"
        table.add_row(
            name,
            preset.description,
            tier_label,
            str(len(preset.coding_standards)),
            str(len(preset.anti_patterns)),
        )

    console.print(table)

    if info.tier == Tier.FREE:
        console.print("\n[dim]Upgrade to Pro for premium presets: https://anchormd.dev/pro[/dim]")


@app.command()
def status() -> None:
    """Show current license status and available features."""
    track_command("status")
    info = get_license_info()
    tier_config = TIER_DEFINITIONS[info.tier]

    tier_style = "green" if info.tier == Tier.PRO else "blue"
    console.print(
        Panel(
            f"  Tier: [{tier_style}]{tier_config.name}[/{tier_style}] "
            f"({tier_config.price_label})\n"
            f"  License: {'Valid' if info.valid else 'None'}\n"
            f"  Features: {len(tier_config.features)}",
            title="AnchorMD License",
            border_style=tier_style,
        )
    )

    table = Table(title="Feature Access")
    table.add_column("Feature", style="bold")
    table.add_column("Status")

    # Show all Pro features with their status.
    pro_config = TIER_DEFINITIONS[Tier.PRO]
    for feature in pro_config.features:
        if feature in tier_config.features:
            table.add_row(feature, "[green]Available[/green]")
        else:
            table.add_row(feature, "[yellow]Pro only[/yellow]")

    console.print(table)

    if info.tier == Tier.FREE:
        console.print("\n[dim]Upgrade to Pro ($8/mo or $69/yr): https://anchormd.dev/pro[/dim]")


@app.command()
def stats(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),  # noqa: B008
) -> None:
    """Show local usage telemetry (requires ANCHORMD_TELEMETRY=1)."""
    track_command("stats")
    from anchormd.telemetry import TelemetryStore, _telemetry_dir, is_enabled

    if not is_enabled():
        console.print(
            "[dim]Telemetry is disabled. "
            "Set ANCHORMD_TELEMETRY=1 to enable local usage tracking.[/dim]"
        )
        return

    db_file = _telemetry_dir() / "telemetry.db"
    if not db_file.exists():
        console.print("[dim]No telemetry data yet.[/dim]")
        return

    ts = TelemetryStore(db_file)
    try:
        commands = ts.get_command_counts()
        pro_gates = ts.get_pro_gate_counts()
        total = ts.get_total_events()
        first = ts.get_first_event_time()
        last = ts.get_last_event_time()
        activity = ts.get_daily_activity()

        if json_output:
            data = {
                "total_events": total,
                "first_event": first,
                "last_event": last,
                "commands": commands,
                "pro_gate_hits": pro_gates,
                "daily_activity": [{"date": d, "count": c} for d, c in activity],
            }
            console.print(json.dumps(data, indent=2))
        else:
            overview = Table(title="Telemetry Overview")
            overview.add_column("Metric", style="cyan")
            overview.add_column("Value", style="green")
            overview.add_row("Total Events", str(total))
            overview.add_row("First Event", first or "n/a")
            overview.add_row("Last Event", last or "n/a")
            console.print(overview)

            if commands:
                cmd_table = Table(title="Command Usage")
                cmd_table.add_column("Command", style="cyan")
                cmd_table.add_column("Count", style="green", justify="right")
                for name, count in commands.items():
                    cmd_table.add_row(name, str(count))
                console.print(cmd_table)

            if pro_gates:
                gate_table = Table(title="Pro Feature Gate Hits")
                gate_table.add_column("Feature", style="cyan")
                gate_table.add_column("Attempts", style="yellow", justify="right")
                for name, count in pro_gates.items():
                    gate_table.add_row(name, str(count))
                console.print(gate_table)

            if activity:
                act_table = Table(title="Daily Activity (Last 7 Days)")
                act_table.add_column("Date", style="cyan")
                act_table.add_column("Events", style="green", justify="right")
                for day, count in activity:
                    act_table.add_row(day, str(count))
                console.print(act_table)
    finally:
        ts.close()


_SOURCE_DIR_CANDIDATES = ("src", "lib", "app", "packages", "pkg", "cmd", "internal")


@app.command(name="tech-debt")
@require_pro("tech_debt")
@require_quota("deep_scan")
def tech_debt(
    path: Path = typer.Argument(Path("."), help="Path to project root"),  # noqa: B008
    output_json: bool = typer.Option(  # noqa: B008
        False, "--json", help="Output results as JSON"
    ),
    verbose: bool = typer.Option(  # noqa: B008
        False, "-v", "--verbose", help="Show all signals, not just priority items"
    ),
    fail_below: int = typer.Option(  # noqa: B008
        0, "--fail-below", help="Exit with code 2 if score is below this threshold"
    ),
    source_only: bool = typer.Option(  # noqa: B008
        False,
        "--source-only",
        help=(
            "Restrict scan to standard source directories "
            "(src, lib, app, packages, pkg, cmd, internal) if present. "
            "Skips archive/docs/content dirs common in knowledge-base-style repos."
        ),
    ),
    include_paths: list[str] = typer.Option(  # noqa: B008
        None,
        "--include-path",
        help=(
            "Restrict scan to these path prefixes (relative to project root). "
            "Repeatable. Overrides --source-only auto-detection."
        ),
    ),
    extra_excludes: list[str] = typer.Option(  # noqa: B008
        None,
        "--exclude",
        help=(
            "Additional directory/file glob patterns to skip. "
            "Repeatable. Merged with default excludes."
        ),
    ),
) -> None:
    """Scan codebase for technical debt signals. [Pro]"""
    track_command("tech_debt")
    try:
        root = path.resolve()
        if not root.is_dir():
            console.print(f"[red]Error:[/red] {root} is not a directory.")
            raise typer.Exit(1)

        source_roots: list[str] = []
        if include_paths:
            source_roots = [p for p in include_paths if p]
        elif source_only:
            source_roots = [d for d in _SOURCE_DIR_CANDIDATES if (root / d).is_dir()]
            if not source_roots:
                console.print(
                    "[yellow]--source-only:[/yellow] no standard source dirs found "
                    f"({', '.join(_SOURCE_DIR_CANDIDATES)}). Scanning full tree."
                )

        config = ForgeConfig(root_path=root, source_roots=source_roots)
        if extra_excludes:
            config.exclude_patterns = list(config.exclude_patterns) + [
                e for e in extra_excludes if e
            ]

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Scanning codebase...", total=None)
            scanner = CodebaseScanner(config)
            structure = scanner.scan()
            progress.update(task, description=f"Scanned {structure.total_files} files")

            task = progress.add_task("Analyzing technical debt...", total=None)
            from anchormd.analyzers.tech_debt import TechDebtAnalyzer

            analyzer = TechDebtAnalyzer()
            result = analyzer.analyze(structure, config)
            progress.update(task, description="Done")

        findings = result.findings
        signals = findings.get("signals", [])
        score = findings.get("score", 100)

        if output_json:
            print(json.dumps(findings, indent=2))  # noqa: T201
        else:
            # Score display
            score_color = "green" if score >= 80 else "yellow" if score >= 50 else "red"
            grade = (
                "A"
                if score >= 90
                else "B"
                if score >= 80
                else "C"
                if score >= 70
                else "D"
                if score >= 50
                else "F"
            )

            console.print()
            console.print(
                Panel(
                    f"  Score: [{score_color}]{score}/100 ({grade})[/{score_color}]\n"
                    f"  Signals: {findings.get('total_signals', 0)}\n"
                    f"  Critical: {findings.get('critical_count', 0)}  "
                    f"High: {findings.get('high_count', 0)}  "
                    f"Medium: {findings.get('medium_count', 0)}  "
                    f"Low: {findings.get('low_count', 0)}",
                    title="Technical Debt Audit",
                    border_style=score_color,
                )
            )

            # Category breakdown
            categories = findings.get("categories", {})
            if categories:
                cat_table = Table(title="Debt by Category")
                cat_table.add_column("Category", style="bold")
                cat_table.add_column("Count", justify="right")
                for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
                    label = cat.replace("_", " ").title()
                    cat_table.add_row(label, str(count))
                console.print(cat_table)

            # Signals
            if signals:
                if verbose:
                    show_signals = signals
                else:
                    show_signals = [s for s in signals if s["severity"] in ("critical", "high")]

                if show_signals:
                    sig_table = Table(title="Priority Items" if not verbose else "All Signals")
                    sig_table.add_column("Severity", style="bold")
                    sig_table.add_column("File")
                    sig_table.add_column("Message")

                    severity_styles = {
                        "critical": "red bold",
                        "high": "red",
                        "medium": "yellow",
                        "low": "blue",
                    }

                    for sig in show_signals[:50]:  # cap display
                        style = severity_styles.get(sig["severity"], "white")
                        loc = sig["file"]
                        if sig.get("line"):
                            loc += f":{sig['line']}"
                        sig_table.add_row(
                            f"[{style}]{sig['severity'].upper()}[/{style}]",
                            loc,
                            sig["message"][:100],
                        )

                    console.print(sig_table)

                    if not verbose:
                        remaining = len(signals) - len(show_signals)
                        if remaining > 0:
                            console.print(
                                f"\n[dim]{remaining} lower-severity signals hidden. "
                                f"Use -v to show all.[/dim]"
                            )

        record_scan_usage("deep_scan", hashlib.sha256(str(root).encode()).hexdigest()[:16])

        if score < fail_below:
            raise typer.Exit(2)

    except ForgeError as e:
        console.print(Panel(str(e), title="Error", border_style="red"))
        raise typer.Exit(1) from e


@app.command(name="opsec")
@require_pro("opsec")
@require_quota("deep_scan")
def opsec(
    path: Path = typer.Argument(Path("."), help="Path to project root"),  # noqa: B008
    output_json: bool = typer.Option(  # noqa: B008
        False, "--json", help="Output results as JSON"
    ),
    verbose: bool = typer.Option(  # noqa: B008
        False, "-v", "--verbose", help="Show all findings, not just critical/high"
    ),
    fail_below: int = typer.Option(  # noqa: B008
        0, "--fail-below", help="Exit with code 2 if score is below this threshold"
    ),
) -> None:
    """Scan codebase for OPSEC leaks: secrets, local paths, strategy docs. [Pro]"""
    track_command("opsec")
    try:
        root = path.resolve()
        if not root.is_dir():
            console.print(f"[red]Error:[/red] {root} is not a directory.")
            raise typer.Exit(1)

        config = ForgeConfig(root_path=root)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Scanning codebase...", total=None)
            scanner = CodebaseScanner(config)
            structure = scanner.scan()
            progress.update(task, description=f"Scanned {structure.total_files} files")

            task = progress.add_task("Running OPSEC scan...", total=None)
            from anchormd.analyzers.opsec import OpsecAnalyzer

            analyzer = OpsecAnalyzer()
            result = analyzer.analyze(structure, config)
            progress.update(task, description="Done")

        findings = result.findings
        all_findings = findings.get("findings", [])
        score = findings.get("score", 100)

        if output_json:
            print(json.dumps(findings, indent=2))  # noqa: T201
        else:
            # Score display
            score_color = "green" if score >= 80 else "yellow" if score >= 50 else "red"
            grade = (
                "A"
                if score >= 90
                else "B"
                if score >= 80
                else "C"
                if score >= 70
                else "D"
                if score >= 50
                else "F"
            )

            console.print()
            console.print(
                Panel(
                    f"  Score: [{score_color}]{score}/100 ({grade})[/{score_color}]\n"
                    f"  Findings: {findings.get('total_findings', 0)}\n"
                    f"  Critical: {findings.get('critical_count', 0)}  "
                    f"High: {findings.get('high_count', 0)}  "
                    f"Medium: {findings.get('medium_count', 0)}  "
                    f"Low: {findings.get('low_count', 0)}",
                    title="OPSEC Scan",
                    border_style=score_color,
                )
            )

            # Category breakdown
            categories = findings.get("categories", {})
            if categories:
                cat_table = Table(title="Findings by Category")
                cat_table.add_column("Category", style="bold")
                cat_table.add_column("Count", justify="right")
                for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
                    label = cat.replace("_", " ").title()
                    cat_table.add_row(label, str(count))
                console.print(cat_table)

            # Findings
            if all_findings:
                if verbose:
                    show = all_findings
                else:
                    show = [f for f in all_findings if f["severity"] in ("critical", "high")]

                if show:
                    tbl = Table(title="Priority Items" if not verbose else "All Findings")
                    tbl.add_column("Severity", style="bold")
                    tbl.add_column("File")
                    tbl.add_column("Message")

                    severity_styles = {
                        "critical": "red bold",
                        "high": "red",
                        "medium": "yellow",
                        "low": "blue",
                    }

                    for f in show[:50]:
                        style = severity_styles.get(f["severity"], "white")
                        loc = f["file"]
                        if f.get("line"):
                            loc += f":{f['line']}"
                        tbl.add_row(
                            f"[{style}]{f['severity'].upper()}[/{style}]",
                            loc,
                            f["message"][:100],
                        )

                    console.print(tbl)

                    if not verbose:
                        remaining = len(all_findings) - len(show)
                        if remaining > 0:
                            console.print(
                                f"\n[dim]{remaining} lower-severity findings hidden. "
                                f"Use -v to show all.[/dim]"
                            )
                else:
                    console.print("\n[green]No critical or high-severity findings.[/green]")

        record_scan_usage("deep_scan", hashlib.sha256(str(root).encode()).hexdigest()[:16])

        if score < fail_below:
            raise typer.Exit(2)

    except ForgeError as e:
        console.print(Panel(str(e), title="Error", border_style="red"))
        raise typer.Exit(1) from e


@app.command(name="github-health")
@require_pro("github_health")
@require_quota("deep_scan")
def github_health(
    path: Path = typer.Argument(Path("."), help="Path to project root"),  # noqa: B008
    output_json: bool = typer.Option(  # noqa: B008
        False, "--json", help="Output results as JSON"
    ),
) -> None:
    """Analyze GitHub repository health via gh CLI. [Pro]"""
    track_command("github_health")
    try:
        root = path.resolve()
        if not root.is_dir():
            console.print(f"[red]Error:[/red] {root} is not a directory.")
            raise typer.Exit(1)

        config = ForgeConfig(root_path=root)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Scanning codebase...", total=None)
            scanner = CodebaseScanner(config)
            structure = scanner.scan()
            progress.update(task, description=f"Scanned {structure.total_files} files")

            task = progress.add_task("Querying GitHub...", total=None)
            from anchormd.analyzers.github import GitHubAnalyzer

            analyzer = GitHubAnalyzer()
            result = analyzer.analyze(structure, config)
            progress.update(task, description="Done")

        findings = result.findings

        if not findings.get("available"):
            console.print(
                f"[yellow]Not a GitHub repo or gh not authenticated:[/yellow] "
                f"{findings.get('reason', 'unknown')}"
            )
            raise typer.Exit(1)

        if output_json:
            print(json.dumps(findings, indent=2, default=str))  # noqa: T201
        else:
            health = findings.get("health_score", 0)
            score_color = "green" if health >= 80 else "yellow" if health >= 50 else "red"

            console.print()
            console.print(
                Panel(
                    f"  Repository: {findings.get('repo', 'unknown')}\n"
                    f"  Health: [{score_color}]{health}/100[/{score_color}]\n"
                    f"  Stars: {findings.get('stars', 0)}  "
                    f"Forks: {findings.get('forks', 0)}\n"
                    f"  License: {findings.get('license') or 'None'}",
                    title="GitHub Health",
                    border_style=score_color,
                )
            )

            # Security
            security = findings.get("security", {})
            if security.get("dependabot_alerts") or security.get("code_scanning_alerts"):
                console.print("\n[red bold]Security Alerts:[/red bold]")
                if security.get("dependabot_alerts"):
                    console.print(f"  Dependabot: {security['dependabot_alerts']}")
                if security.get("code_scanning_alerts"):
                    console.print(f"  Code Scanning: {security['code_scanning_alerts']}")

            # Issues & PRs
            issues = findings.get("issues", {})
            prs = findings.get("pull_requests", {})

            issue_table = Table(title="Issues & PRs")
            issue_table.add_column("Metric", style="bold")
            issue_table.add_column("Count", justify="right")
            issue_table.add_row("Open Issues", str(issues.get("open", 0)))
            issue_table.add_row("Stale Issues (>90d)", str(issues.get("stale_90d", 0)))
            issue_table.add_row("Open PRs", str(prs.get("open", 0)))
            issue_table.add_row("Draft PRs", str(prs.get("draft", 0)))
            issue_table.add_row("Stale PRs (>30d)", str(prs.get("stale_30d", 0)))
            console.print(issue_table)

            # CI
            workflows = findings.get("workflows", {})
            failing = workflows.get("failing", [])
            if failing:
                console.print("\n[red bold]Failing CI Workflows:[/red bold]")
                for wf in failing:
                    console.print(f"  [red]FAIL[/red] {wf}")

            # Branch protection
            protection = findings.get("branch_protection", {})
            if not protection.get("enabled"):
                console.print(
                    f"\n[yellow]Warning:[/yellow] No branch protection on "
                    f"`{findings.get('default_branch', 'main')}`"
                )

        record_scan_usage("deep_scan", hashlib.sha256(str(root).encode()).hexdigest()[:16])

    except ForgeError as e:
        console.print(Panel(str(e), title="Error", border_style="red"))
        raise typer.Exit(1) from e


@app.command()
@require_pro("cleanup")
@require_quota("deep_scan")
def cleanup(
    path: Path = typer.Argument(Path("."), help="Path to project root"),  # noqa: B008
    execute: bool = typer.Option(  # noqa: B008
        False, "--execute", help="Actually perform cleanup (default is dry-run)"
    ),
    stale_issues: int = typer.Option(  # noqa: B008
        90, "--stale-issues", help="Days before an issue is considered stale"
    ),
    stale_prs: int = typer.Option(  # noqa: B008
        30, "--stale-prs", help="Days before a PR is considered stale"
    ),
    include_drafts: bool = typer.Option(  # noqa: B008
        False, "--include-drafts", help="Also close stale draft PRs"
    ),
    no_branches: bool = typer.Option(  # noqa: B008
        False, "--no-branches", help="Skip merged branch deletion"
    ),
    output_json: bool = typer.Option(  # noqa: B008
        False, "--json", help="Output plan/results as JSON"
    ),
) -> None:
    """Clean up stale GitHub artifacts (issues, PRs, branches). [Pro]

    Dry-run by default. Use --execute to apply changes.
    """
    track_command("cleanup")
    try:
        root = path.resolve()
        if not root.is_dir():
            console.print(f"[red]Error:[/red] {root} is not a directory.")
            raise typer.Exit(1)

        from anchormd.cleanup import CleanupAgent

        agent = CleanupAgent(
            cwd=str(root),
            stale_issue_days=stale_issues,
            stale_pr_days=stale_prs,
            delete_merged_branches=not no_branches,
            close_draft_prs=include_drafts,
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Building cleanup plan...", total=None)
            plan = agent.plan()
            progress.update(task, description=f"Found {plan.total} actions")

        if plan.total == 0:
            if output_json:
                print(json.dumps({"actions": [], "message": "Nothing to clean up"}))  # noqa: T201
            else:
                console.print("[green]Nothing to clean up — repository is tidy.[/green]")
            return

        if output_json and not execute:
            print(  # noqa: T201
                json.dumps(
                    {
                        "dry_run": True,
                        "actions": [
                            {
                                "action": a.action,
                                "target": a.target,
                                "reason": a.reason,
                            }
                            for a in plan.actions
                        ],
                    },
                    indent=2,
                )
            )
            return

        # Display plan
        if not output_json:
            plan_table = Table(title="Cleanup Plan" + (" [DRY RUN]" if not execute else ""))
            plan_table.add_column("Action", style="bold")
            plan_table.add_column("Target")
            plan_table.add_column("Reason")

            action_styles = {
                "close_issue": "yellow",
                "close_pr": "yellow",
                "delete_branch": "red",
            }

            for action in plan.actions:
                style = action_styles.get(action.action, "white")
                label = action.action.replace("_", " ").title()
                plan_table.add_row(
                    f"[{style}]{label}[/{style}]",
                    action.target,
                    action.reason,
                )

            console.print(plan_table)

        if not execute:
            if not output_json:
                console.print(
                    f"\n[dim]{plan.total} actions planned. Run with --execute to apply.[/dim]"
                )
            return

        # Execute
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Executing cleanup...", total=None)
            plan = agent.execute(plan)
            progress.update(task, description="Done")

        if output_json:
            print(  # noqa: T201
                json.dumps(
                    {
                        "dry_run": False,
                        "executed": plan.executed_count,
                        "errors": plan.error_count,
                        "actions": [
                            {
                                "action": a.action,
                                "target": a.target,
                                "executed": a.executed,
                                "error": a.error,
                            }
                            for a in plan.actions
                        ],
                    },
                    indent=2,
                )
            )
        else:
            console.print(f"\n[green]Executed {plan.executed_count}/{plan.total} actions.[/green]")
            if plan.error_count:
                console.print(f"[red]{plan.error_count} errors:[/red]")
                for action in plan.actions:
                    if action.error:
                        console.print(f"  {action.target}: {action.error}")

        record_scan_usage("deep_scan", hashlib.sha256(str(root).encode()).hexdigest()[:16])

    except ForgeError as e:
        console.print(Panel(str(e), title="Error", border_style="red"))
        raise typer.Exit(1) from e
