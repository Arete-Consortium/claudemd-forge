"""Report rendering for drift detection results."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from anchormd.drift.models import DriftSeverity, RunRecord

_SEVERITY_STYLES = {
    DriftSeverity.CRITICAL: "red",
    DriftSeverity.WARNING: "yellow",
    DriftSeverity.STABLE: "green",
    DriftSeverity.IMPROVED: "cyan",
}


def render_terminal_report(
    run: RunRecord,
    baseline: RunRecord | None = None,
    console: Console | None = None,
) -> None:
    """Render a drift report to the terminal using Rich."""
    if console is None:
        console = Console()

    severity_style = _SEVERITY_STYLES.get(run.severity, "white")

    console.print(
        Panel(
            f"  Model: {run.model}\n"
            f"  Score: [{severity_style}]{run.score:.2f}[/{severity_style}]\n"
            f"  Delta: {run.delta:+.2f}\n"
            f"  Severity: [{severity_style}]{run.severity.upper()}[/{severity_style}]\n"
            f"  Timestamp: {run.timestamp}",
            title="Drift Report",
            border_style=severity_style,
        )
    )

    if run.results:
        table = Table(title="Benchmark Results")
        table.add_column("Benchmark", style="bold")
        table.add_column("Score")
        table.add_column("Checks")
        table.add_column("Status")

        for result in run.results:
            passed = sum(1 for c in result.checks if c.passed)
            total = len(result.checks)
            if result.score >= 0.8:
                score_style, status = "green", "PASS"
            elif result.score >= 0.5:
                score_style, status = "yellow", "WARN"
            else:
                score_style, status = "red", "FAIL"
            table.add_row(
                result.benchmark_id,
                f"[{score_style}]{result.score:.2f}[/{score_style}]",
                f"{passed}/{total}",
                f"[{score_style}]{status}[/{score_style}]",
            )

        console.print(table)

    # Show failing checks detail.
    failing = [r for r in run.results if any(not c.passed for c in r.checks)]
    if failing:
        console.print("\n[bold]Failing Checks:[/bold]")
        for result in failing:
            for check in result.checks:
                if not check.passed:
                    console.print(f"  [red]x[/red] {result.benchmark_id}: {check.message}")


def render_json_report(run: RunRecord) -> str:
    """Render a machine-readable JSON report."""
    return json.dumps(
        {
            "run_id": run.run_id,
            "timestamp": run.timestamp,
            "model": run.model,
            "score": run.score,
            "delta": run.delta,
            "severity": str(run.severity),
            "results": [
                {
                    "benchmark_id": r.benchmark_id,
                    "score": r.score,
                    "checks": [
                        {
                            "type": str(c.type),
                            "passed": c.passed,
                            "message": c.message,
                        }
                        for c in r.checks
                    ],
                }
                for r in run.results
            ],
        },
        indent=2,
    )


def render_html_report(history: list[RunRecord]) -> str:
    """Render an HTML report with Chart.js trend visualization."""
    try:
        from jinja2 import Environment, FileSystemLoader
    except ImportError as exc:
        from anchormd.exceptions import DriftError

        raise DriftError("jinja2 required for HTML reports") from exc

    template_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=True)
    template = env.get_template("report.html")

    labels = [r.timestamp[:10] for r in history]
    scores = [r.score for r in history]
    deltas = [r.delta for r in history]
    severities = [str(r.severity) for r in history]

    return template.render(
        history=history,
        labels=json.dumps(labels),
        scores=json.dumps(scores),
        deltas=json.dumps(deltas),
        severities=json.dumps(severities),
    )
