"""CLI commands for agent drift detection."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console

from anchormd.exceptions import ForgeError
from anchormd.gates import require_pro
from anchormd.telemetry import track_command

drift_app = typer.Typer(
    name="drift",
    help="Agent behavioral drift detection.",
    no_args_is_help=True,
)
console = Console()

_SAMPLE_BENCHMARK = """\
version: 1
benchmarks:
  - id: code_style_snake_case
    prompt: "Write a Python function that calculates the average of a list of numbers."
    checks:
      - type: pattern_present
        pattern: "def [a-z_]+\\\\("
        message: "Function should use snake_case naming"
      - type: pattern_absent
        pattern: "def [A-Z]"
        message: "Function should not use PascalCase"
    weight: 1.0

  - id: error_handling
    prompt: "Write a Python function that reads a JSON file and returns the parsed data."
    checks:
      - type: pattern_present
        pattern: "try:"
        message: "Should include error handling"
      - type: pattern_present
        pattern: "except"
        message: "Should catch exceptions"
      - type: pattern_absent
        pattern: "except:"
        message: "Should not use bare except"
    weight: 1.0

  - id: type_hints
    prompt: "Write a Python function that merges two dictionaries."
    checks:
      - type: pattern_present
        pattern: "-> dict"
        message: "Should include return type hint"
      - type: pattern_present
        pattern: "def \\\\w+\\\\(.*:.*\\\\)"
        message: "Should include parameter type hints"
    weight: 1.0
"""


@drift_app.command()
def init(
    path: Path = typer.Argument(Path("."), help="Path to project root"),  # noqa: B008
) -> None:
    """Initialize drift detection with sample benchmarks."""
    track_command("drift_init")
    try:
        from anchormd.drift.storage import ensure_dirs, load_benchmarks

        root = path.resolve()
        ensure_dirs(root)

        benchmarks_dir = root / ".anchormd" / "benchmarks"
        sample_file = benchmarks_dir / "default.yaml"

        if sample_file.exists():
            console.print("[yellow]Benchmark file already exists.[/yellow]")
            return

        sample_file.write_text(_SAMPLE_BENCHMARK)
        console.print(f"[green]Created {sample_file.relative_to(root)}[/green]")

        # Verify it parses.
        suites = load_benchmarks(root)
        total = sum(len(s.benchmarks) for s in suites)
        console.print(f"  {total} benchmarks ready.")
        console.print("\nNext: [bold]anchormd drift run --model <model>[/bold]")

    except ForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@drift_app.command()
def run(
    path: Path = typer.Argument(Path("."), help="Path to project root"),  # noqa: B008
    model: str = typer.Option(  # noqa: B008
        ..., "--model", "-m", help="Model to benchmark (e.g. ollama/llama3, claude-3-haiku)"
    ),
    judge_model: str | None = typer.Option(  # noqa: B008
        None, "--judge-model", "-j", help="Model for LLM judge checks [Pro]"
    ),
) -> None:
    """Run drift benchmarks against a model."""
    track_command("drift_run")
    try:
        from anchormd.drift.adapters import get_adapter
        from anchormd.drift.models import DriftSeverity, RunRecord
        from anchormd.drift.reporter import render_terminal_report
        from anchormd.drift.runner import run_benchmarks
        from anchormd.drift.scorer import (
            classify_severity,
            compute_delta,
            score_run,
        )
        from anchormd.drift.storage import (
            load_baseline,
            load_benchmarks,
            save_run,
        )
        from anchormd.licensing import has_feature

        root = path.resolve()
        suites = load_benchmarks(root)
        if not suites:
            console.print("[yellow]No benchmarks found. Run 'drift init' first.[/yellow]")
            raise typer.Exit(1)

        adapter = get_adapter(model)
        total = sum(len(s.benchmarks) for s in suites)
        console.print(f"Running {total} benchmarks against {adapter.name()}...")

        # Judge adapter (Pro only).
        judge = None
        has_pro = has_feature("drift_llm_judge")
        if judge_model:
            if not has_pro:
                console.print("[yellow]LLM judge requires Pro tier.[/yellow]")
            else:
                judge = get_adapter(judge_model)

        results = run_benchmarks(adapter, suites, judge=judge, has_pro=has_pro)

        # Flatten benchmarks for scoring.
        all_benchmarks = [b for s in suites for b in s.benchmarks]
        run_score = score_run(results, all_benchmarks)

        # Compare to baseline.
        baseline = load_baseline(root)
        baseline_score = baseline.score if baseline else None
        delta = compute_delta(run_score, baseline_score)
        severity = classify_severity(delta)

        record = RunRecord(
            run_id=uuid.uuid4().hex[:12],
            timestamp=datetime.now(UTC).isoformat(),
            model=adapter.name(),
            score=run_score,
            delta=delta,
            severity=severity,
            results=results,
        )

        save_run(root, record)
        render_terminal_report(record, baseline, console=console)

        if severity == DriftSeverity.CRITICAL:
            console.print("\n[red bold]CRITICAL drift detected![/red bold]")

    except ForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@drift_app.command()
def report(
    path: Path = typer.Argument(Path("."), help="Path to project root"),  # noqa: B008
    ci: bool = typer.Option(False, "--ci", help="CI mode: exit 1 on critical [Pro]"),  # noqa: B008
    output_json: bool = typer.Option(False, "--json", help="Output JSON report"),  # noqa: B008
    html: str | None = typer.Option(  # noqa: B008
        None, "--html", help="Write HTML report to file [Pro]"
    ),
) -> None:
    """Show the latest drift report."""
    track_command("drift_report")
    try:
        from anchormd.drift.reporter import (
            render_html_report,
            render_json_report,
            render_terminal_report,
        )
        from anchormd.drift.storage import load_baseline, load_history
        from anchormd.licensing import has_feature

        root = path.resolve()
        history = load_history(root)
        if not history:
            console.print("[yellow]No run history. Run 'drift run' first.[/yellow]")
            raise typer.Exit(1)

        latest = history[-1]
        baseline = load_baseline(root)

        if output_json:
            print(render_json_report(latest))  # noqa: T201
        elif html:
            if not has_feature("drift_html_report"):
                console.print("[yellow]HTML reports require Pro tier.[/yellow]")
                raise typer.Exit(1)
            html_content = render_html_report(history)
            Path(html).write_text(html_content)
            console.print(f"[green]HTML report written to {html}[/green]")
        else:
            render_terminal_report(latest, baseline, console=console)

        if ci:
            if not has_feature("drift_ci"):
                console.print("[yellow]CI mode requires Pro tier.[/yellow]")
                raise typer.Exit(1)
            if latest.severity.value == "critical":
                raise typer.Exit(1)

    except ForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@drift_app.command()
def baseline(
    path: Path = typer.Argument(Path("."), help="Path to project root"),  # noqa: B008
) -> None:
    """Set the latest run as the new baseline."""
    track_command("drift_baseline")
    try:
        from anchormd.drift.storage import load_history, save_baseline

        root = path.resolve()
        history = load_history(root)
        if not history:
            console.print("[yellow]No run history. Run 'drift run' first.[/yellow]")
            raise typer.Exit(1)

        latest = history[-1]
        save_baseline(root, latest)
        console.print(
            f"[green]Baseline set:[/green] score={latest.score:.2f} "
            f"model={latest.model} ({latest.timestamp[:10]})"
        )

    except ForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@drift_app.command()
def trend(
    path: Path = typer.Argument(Path("."), help="Path to project root"),  # noqa: B008
) -> None:
    """Show score trend over time."""
    track_command("drift_trend")
    try:
        from anchormd.drift.storage import load_history
        from anchormd.drift.trend import render_ascii_trend

        root = path.resolve()
        history = load_history(root)
        console.print(render_ascii_trend(history))

    except ForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@drift_app.command()
@require_pro("drift_generate")
def generate(
    path: Path = typer.Argument(Path("."), help="Path to project root"),  # noqa: B008
    source: str = typer.Option(  # noqa: B008
        "CLAUDE.md", "--from", help="Source file to generate benchmarks from"
    ),
    model: str = typer.Option(  # noqa: B008
        ..., "--model", "-m", help="Model to use for generation"
    ),
) -> None:
    """Generate benchmarks from a CLAUDE.md file. [Pro]"""
    track_command("drift_generate")
    try:
        from anchormd.drift.adapters import get_adapter
        from anchormd.drift.generator import generate_benchmarks
        from anchormd.drift.storage import save_benchmarks

        root = path.resolve()
        source_path = root / source
        if not source_path.is_file():
            console.print(f"[red]File not found:[/red] {source_path}")
            raise typer.Exit(1)

        content = source_path.read_text()
        adapter = get_adapter(model)

        console.print(f"Generating benchmarks from {source} using {adapter.name()}...")
        suite = generate_benchmarks(content, adapter)

        save_benchmarks(root, suite, "generated.yaml")
        console.print(
            f"[green]Generated {len(suite.benchmarks)} benchmarks → "
            f".anchormd/benchmarks/generated.yaml[/green]"
        )

    except ForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@drift_app.command()
@require_pro("drift_fix")
def fix(
    path: Path = typer.Argument(Path("."), help="Path to project root"),  # noqa: B008
    model: str = typer.Option(  # noqa: B008
        ..., "--model", "-m", help="Model to use for suggestions"
    ),
) -> None:
    """Suggest CLAUDE.md fixes for failing benchmarks. [Pro]"""
    track_command("drift_fix")
    try:
        from anchormd.drift.adapters import get_adapter
        from anchormd.drift.fixer import suggest_fixes
        from anchormd.drift.storage import load_history

        root = path.resolve()
        history = load_history(root)
        if not history:
            console.print("[yellow]No run history. Run 'drift run' first.[/yellow]")
            raise typer.Exit(1)

        latest = history[-1]
        adapter = get_adapter(model)

        console.print(f"Analyzing failures from run {latest.run_id}...")
        suggestions = suggest_fixes(latest, history, adapter)

        if not suggestions:
            console.print("[green]No failing benchmarks — nothing to fix![/green]")
            return

        console.print(f"\n[bold]{len(suggestions)} fix suggestion(s):[/bold]\n")
        for i, s in enumerate(suggestions, 1):
            console.print(f"  {i}. [bold]{s.benchmark_id}[/bold] — {s.description}")
            console.print(f"     Confidence: {s.confidence:.0%}")
            console.print("     Add to CLAUDE.md:")
            console.print(f"     [dim]{s.claude_md_addition}[/dim]\n")

    except ForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
