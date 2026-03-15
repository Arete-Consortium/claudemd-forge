"""Trend visualization and aggregation for drift history."""

from __future__ import annotations

from anchormd.drift.models import RunRecord


def aggregate_trend(history: list[RunRecord]) -> list[dict]:
    """Aggregate run history into trend data points."""
    return [
        {
            "run_id": r.run_id,
            "timestamp": r.timestamp,
            "model": r.model,
            "score": r.score,
            "delta": r.delta,
            "severity": str(r.severity),
        }
        for r in history
    ]


def render_ascii_trend(history: list[RunRecord], width: int = 60) -> str:
    """Render an ASCII chart of score history.

    Returns a multi-line string showing scores over time.
    """
    if not history:
        return "No run history available."

    lines: list[str] = []
    lines.append("Score Trend")
    lines.append("=" * (width + 20))

    scores = [r.score for r in history]
    min_score = min(scores)
    max_score = max(scores)
    score_range = max_score - min_score if max_score != min_score else 1.0

    # Y-axis labels.
    lines.append(f"  1.00 |{'':>{width}}|")

    for record in history:
        # Normalize score to bar width.
        normalized = (record.score - min_score) / score_range if score_range > 0 else 0.5
        bar_len = max(1, int(normalized * width))
        bar = "#" * bar_len

        # Severity indicator.
        indicator = {
            "critical": "!",
            "warning": "~",
            "stable": " ",
            "improved": "+",
        }.get(str(record.severity), " ")

        date = record.timestamp[:10]
        delta_str = f"{record.delta:+.2f}" if record.delta != 0.0 else " 0.00"
        lines.append(f"  {record.score:.2f} |{bar:<{width}}| {date} {delta_str} {indicator}")

    lines.append(f"  0.00 |{'':>{width}}|")
    lines.append("=" * (width + 20))
    lines.append(
        f"  Runs: {len(history)} | "
        f"Latest: {scores[-1]:.2f} | "
        f"Best: {max_score:.2f} | "
        f"Worst: {min_score:.2f}"
    )

    return "\n".join(lines)
