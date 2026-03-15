"""Fix suggestion engine for failing drift benchmarks.

Pro feature: uses an LLM to analyze failing checks and suggest
CLAUDE.md additions to improve compliance.
"""

from __future__ import annotations

import json
import logging
import re

from pydantic import BaseModel

from anchormd.drift.adapters.base import ModelAdapter
from anchormd.drift.models import RunRecord
from anchormd.exceptions import DriftError

logger = logging.getLogger(__name__)


class FixSuggestion(BaseModel):
    """A suggested fix for a failing benchmark."""

    benchmark_id: str
    description: str
    claude_md_addition: str
    confidence: float


_FIXER_PROMPT = """\
You are an expert at writing CLAUDE.md instructions for AI coding assistants.

The following benchmarks are failing. Analyze the failures and suggest CLAUDE.md additions
that would help an AI assistant pass these checks.

## Failing Benchmarks
{failures}

## Instructions
For each failing benchmark, suggest a concise CLAUDE.md addition (1-3 lines) that would
address the root cause. Focus on clear, actionable instructions.

Respond with ONLY a JSON array:
[
  {{
    "benchmark_id": "the_benchmark_id",
    "description": "What this fixes",
    "claude_md_addition": "The text to add to CLAUDE.md",
    "confidence": 0.8
  }}
]
"""


def suggest_fixes(
    run: RunRecord,
    history: list[RunRecord],
    adapter: ModelAdapter,
) -> list[FixSuggestion]:
    """Generate fix suggestions for failing benchmarks.

    Analyzes the current run's failures, considers history trends,
    and uses an LLM to suggest CLAUDE.md additions.
    """
    # Collect failing benchmarks.
    failures: list[dict] = []
    for result in run.results:
        failing_checks = [c for c in result.checks if not c.passed]
        if failing_checks:
            failures.append(
                {
                    "benchmark_id": result.benchmark_id,
                    "score": result.score,
                    "failing_checks": [
                        {"type": str(c.type), "message": c.message} for c in failing_checks
                    ],
                }
            )

    if not failures:
        return []

    prompt = _FIXER_PROMPT.format(failures=json.dumps(failures, indent=2))

    try:
        response = adapter.complete(prompt)
    except Exception as exc:
        raise DriftError(f"Failed to generate fix suggestions: {exc}") from exc

    # Parse JSON response.
    try:
        data = json.loads(response)
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", response)
        if match:
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError as exc:
                raise DriftError(f"LLM returned unparseable JSON: {response[:200]}") from exc
        else:
            raise DriftError(f"LLM returned no JSON: {response[:200]}") from None

    suggestions: list[FixSuggestion] = []
    for item in data:
        try:
            suggestions.append(FixSuggestion.model_validate(item))
        except Exception:
            logger.warning("Skipping invalid fix suggestion: %s", item)

    return suggestions
