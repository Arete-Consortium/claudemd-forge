"""CLI entrypoint for ClaudeMD Forge."""

from __future__ import annotations

import difflib
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from claudemd_forge import __version__
from claudemd_forge.analyzers import run_all
from claudemd_forge.exceptions import ForgeError
from claudemd_forge.gates import check_preset_access, require_pro
from claudemd_forge.generators.composer import DocumentComposer
from claudemd_forge.licensing import (
    PRO_PRESETS,
    TIER_DEFINITIONS,
    Tier,
    get_license_info,
)
from claudemd_forge.models import ForgeConfig
from claudemd_forge.scanner import CodebaseScanner

app = typer.Typer(
    name="claudemd-forge",
    help="Generate and audit CLAUDE.md files for AI coding agents.",
    no_args_is_help=True,
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"claudemd-forge {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(  # noqa: B008
        False, "--version", "-V", help="Show version", callback=_version_callback, is_eager=True
    ),
) -> None:
    """ClaudeMD Forge — Generate and audit CLAUDE.md files for AI coding agents."""


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
            score = composer.estimate_quality_score(content)

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
                    title="ClaudeMD Forge",
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
) -> None:
    """Audit an existing CLAUDE.md file for gaps and improvements."""
    try:
        target = path.resolve()
        if not target.is_file():
            console.print(f"[red]Error:[/red] {target} is not a file.")
            raise typer.Exit(1)

        claude_content = target.read_text()
        project_root = target.parent

        config = ForgeConfig(root_path=project_root)
        scanner = CodebaseScanner(config)
        structure = scanner.scan()
        analyses = run_all(structure, config)

        # Lazy import to avoid circular.
        from claudemd_forge.generators.auditor import ClaudeMdAuditor

        auditor = ClaudeMdAuditor(config)
        report = auditor.audit(claude_content, structure, analyses)

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
        score_color = "green" if report.score >= 70 else "yellow" if report.score >= 40 else "red"
        console.print(f"\n[{score_color}]Score: {report.score}/100[/{score_color}]")

        if report.recommendations:
            console.print("\n[bold]Recommendations:[/bold]")
            for rec in report.recommendations:
                console.print(f"  - {rec}")

        if report.score < 40:
            raise typer.Exit(2)

    except ForgeError as e:
        console.print(Panel(str(e), title="Error", border_style="red"))
        raise typer.Exit(1) from e


@app.command()
@require_pro("init_interactive")
def init(
    path: Path = typer.Argument(Path("."), help="Path to project root"),  # noqa: B008
) -> None:
    """Initialize a CLAUDE.md with interactive prompts. [Pro]"""
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
            content = content.replace(
                f"{root.name} — TODO: Add project description.",
                description,
            )

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
    from claudemd_forge.templates.presets import PRESET_PACKS

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
        console.print(
            "\n[dim]Upgrade to Pro for premium presets: https://claudemd-forge.dev/pro[/dim]"
        )


@app.command()
def frameworks() -> None:
    """List available framework presets."""
    from claudemd_forge.templates.frameworks import (
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
        console.print(
            "\n[dim]Upgrade to Pro for premium presets: https://claudemd-forge.dev/pro[/dim]"
        )


@app.command()
def status() -> None:
    """Show current license status and available features."""
    info = get_license_info()
    tier_config = TIER_DEFINITIONS[info.tier]

    tier_style = "green" if info.tier == Tier.PRO else "blue"
    console.print(
        Panel(
            f"  Tier: [{tier_style}]{tier_config.name}[/{tier_style}] "
            f"({tier_config.price_label})\n"
            f"  License: {'Valid' if info.valid else 'None'}\n"
            f"  Features: {len(tier_config.features)}",
            title="ClaudeMD Forge License",
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
        console.print(
            "\n[dim]Upgrade to Pro ($8/mo or $69/yr): https://claudemd-forge.dev/pro[/dim]"
        )
