"""Benchmark generator — creates benchmark suites from CLAUDE.md content.

Pro feature: uses an LLM to analyze CLAUDE.md rules and generate
appropriate benchmark prompts with checks.
"""

from __future__ import annotations

import json
import logging
import re

from anchormd.drift.adapters.base import ModelAdapter
from anchormd.drift.models import (
    BenchmarkCheck,
    BenchmarkDef,
    BenchmarkSuite,
    CheckType,
)
from anchormd.exceptions import DriftError

logger = logging.getLogger(__name__)

_GENERATOR_PROMPT = """\
You are an expert at creating behavioral benchmarks for AI coding assistants.

Given the following CLAUDE.md content (instructions for an AI assistant), generate a benchmark suite
that tests whether an AI assistant follows these rules.

For each important rule or instruction, create a benchmark with:
1. A unique id (snake_case, descriptive)
2. A prompt that would test the rule
3. One or more checks (pattern_present, pattern_absent, length_range, contains_sections)

## CLAUDE.md Content
{content}

## Output Format
Respond with ONLY a JSON object matching this schema:
{{
  "version": 1,
  "benchmarks": [
    {{
      "id": "rule_name_test",
      "prompt": "The prompt to send to the AI",
      "checks": [
        {{"type": "pattern_present", "pattern": "regex_pattern", "message": "what this checks"}},
        {{"type": "pattern_absent", "pattern": "regex_pattern", "message": "what this checks"}},
        {{"type": "length_range", "min_words": 10, "max_words": 500}},
        {{"type": "contains_sections", "sections": ["Section1", "Section2"]}}
      ],
      "weight": 1.0
    }}
  ]
}}

Generate 3-8 benchmarks covering the most important rules. Focus on testable behaviors.
"""


def generate_benchmarks(
    claude_md_content: str,
    adapter: ModelAdapter,
) -> BenchmarkSuite:
    """Generate a benchmark suite from CLAUDE.md content using an LLM.

    Raises DriftError if the LLM response cannot be parsed.
    """
    prompt = _GENERATOR_PROMPT.format(content=claude_md_content)

    try:
        response = adapter.complete(prompt)
    except Exception as exc:
        raise DriftError(f"Failed to generate benchmarks: {exc}") from exc

    # Parse JSON response — handle markdown fences and preamble.
    try:
        data = json.loads(response)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", response)
        if match:
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError as exc:
                raise DriftError(f"LLM returned unparseable JSON: {response[:200]}") from exc
        else:
            raise DriftError(f"LLM returned no JSON: {response[:200]}") from None

    # Validate and build models.
    try:
        benchmarks: list[BenchmarkDef] = []
        for b in data.get("benchmarks", []):
            checks: list[BenchmarkCheck] = []
            for c in b.get("checks", []):
                check_type = c.get("type", "")
                try:
                    ct = CheckType(check_type)
                except ValueError:
                    logger.warning("Skipping unknown check type: %s", check_type)
                    continue
                checks.append(
                    BenchmarkCheck(
                        type=ct,
                        pattern=c.get("pattern"),
                        message=c.get("message"),
                        criteria=c.get("criteria"),
                        threshold=c.get("threshold", 0.8),
                        min_words=c.get("min_words"),
                        max_words=c.get("max_words"),
                        sections=c.get("sections"),
                    )
                )
            benchmarks.append(
                BenchmarkDef(
                    id=b["id"],
                    prompt=b["prompt"],
                    checks=checks,
                    weight=b.get("weight", 1.0),
                )
            )

        return BenchmarkSuite(version=data.get("version", 1), benchmarks=benchmarks)
    except (KeyError, TypeError) as exc:
        raise DriftError(f"Failed to build benchmark suite from LLM output: {exc}") from exc
