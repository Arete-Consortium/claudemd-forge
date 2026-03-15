"""Benchmark runner — executes prompts against an LLM and evaluates checks."""

from __future__ import annotations

import json
import logging
import re

from anchormd.drift.adapters.base import ModelAdapter
from anchormd.drift.models import (
    BenchmarkCheck,
    BenchmarkResult,
    BenchmarkSuite,
    CheckResult,
    CheckType,
)
from anchormd.drift.scorer import score_benchmark

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Check executors
# ---------------------------------------------------------------------------


def _check_pattern_present(output: str, pattern: str) -> bool:
    """Return True if *pattern* (regex) matches anywhere in *output*."""
    return bool(re.search(pattern, output, re.IGNORECASE | re.DOTALL))


def _check_pattern_absent(output: str, pattern: str) -> bool:
    """Return True if *pattern* (regex) does NOT match in *output*."""
    return not re.search(pattern, output, re.IGNORECASE | re.DOTALL)


def _check_length_range(output: str, min_w: int | None, max_w: int | None) -> bool:
    """Return True if word count is within [min_w, max_w]."""
    word_count = len(output.split())
    if min_w is not None and word_count < min_w:
        return False
    return not (max_w is not None and word_count > max_w)


def _check_json_valid(output: str) -> bool:
    """Return True if *output* contains valid JSON."""
    # Try the whole output first, then extract fenced blocks.
    try:
        json.loads(output)
        return True
    except json.JSONDecodeError:
        pass

    # Try to find a JSON block in markdown fences.
    match = re.search(r"```(?:json)?\s*\n(.*?)```", output, re.DOTALL)
    if match:
        try:
            json.loads(match.group(1))
            return True
        except json.JSONDecodeError:
            pass

    return False


def _check_contains_sections(output: str, sections: list[str]) -> bool:
    """Return True if all *sections* appear as headings in *output*."""
    lower = output.lower()
    for section in sections:
        # Check markdown headings or plain text headings.
        patterns = [
            f"# {section.lower()}",
            f"## {section.lower()}",
            f"### {section.lower()}",
            f"**{section.lower()}**",
        ]
        if not any(p in lower for p in patterns):
            return False
    return True


def _check_llm_judge(
    output: str,
    criteria: str,
    judge: ModelAdapter,
    threshold: float,
) -> tuple[bool, float]:
    """Use an LLM judge to score output against criteria.

    Returns (passed, score) where score is 0.0-1.0.
    """
    judge_prompt = (
        "You are evaluating an AI assistant's output against specific criteria.\n\n"
        f"## Criteria\n{criteria}\n\n"
        f"## Output to evaluate\n{output}\n\n"
        "Rate the output on a scale of 0.0 to 1.0 where 1.0 means perfectly meets criteria.\n"
        'Respond with ONLY a JSON object: {"score": <float>, "reasoning": "<brief>"}'
    )

    try:
        response = judge.complete(judge_prompt)
        # Parse JSON — handle markdown fences and preamble.
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", response)
            if match:
                data = json.loads(match.group(0))
            else:
                logger.warning("LLM judge returned unparseable response")
                return False, 0.0

        score = float(data.get("score", 0.0))
        score = max(0.0, min(1.0, score))
        return score >= threshold, score
    except Exception:
        logger.warning("LLM judge check failed", exc_info=True)
        return False, 0.0


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


def _execute_check(
    check: BenchmarkCheck,
    output: str,
    judge: ModelAdapter | None = None,
    has_pro: bool = False,
) -> CheckResult:
    """Execute a single check against the output."""
    if check.type == CheckType.PATTERN_PRESENT:
        passed = _check_pattern_present(output, check.pattern or "")
        return CheckResult(
            type=check.type,
            passed=passed,
            message=check.message
            or (f"Pattern {'found' if passed else 'not found'}: {check.pattern}"),
        )

    if check.type == CheckType.PATTERN_ABSENT:
        passed = _check_pattern_absent(output, check.pattern or "")
        return CheckResult(
            type=check.type,
            passed=passed,
            message=check.message
            or (f"Pattern {'absent' if passed else 'present'}: {check.pattern}"),
        )

    if check.type == CheckType.LENGTH_RANGE:
        passed = _check_length_range(output, check.min_words, check.max_words)
        word_count = len(output.split())
        return CheckResult(
            type=check.type,
            passed=passed,
            message=check.message
            or (f"Word count {word_count} (range: {check.min_words}-{check.max_words})"),
        )

    if check.type == CheckType.JSON_VALID:
        passed = _check_json_valid(output)
        return CheckResult(
            type=check.type,
            passed=passed,
            message=check.message or f"JSON {'valid' if passed else 'invalid'}",
        )

    if check.type == CheckType.CONTAINS_SECTIONS:
        sections = check.sections or []
        passed = _check_contains_sections(output, sections)
        return CheckResult(
            type=check.type,
            passed=passed,
            message=check.message
            or (f"Sections {'all present' if passed else 'missing'}: {sections}"),
        )

    if check.type == CheckType.LLM_JUDGE:
        if not has_pro:
            return CheckResult(
                type=check.type,
                passed=False,
                message="LLM judge requires Pro tier (skipped)",
                score=0.0,
            )
        if judge is None:
            return CheckResult(
                type=check.type,
                passed=False,
                message="No judge model provided (skipped)",
                score=0.0,
            )
        passed, score = _check_llm_judge(output, check.criteria or "", judge, check.threshold)
        return CheckResult(
            type=check.type,
            passed=passed,
            message=check.message or f"LLM judge score: {score:.2f} (threshold: {check.threshold})",
            score=score,
        )

    return CheckResult(type=check.type, passed=False, message=f"Unknown check type: {check.type}")


def run_benchmarks(
    adapter: ModelAdapter,
    suites: list[BenchmarkSuite],
    judge: ModelAdapter | None = None,
    has_pro: bool = False,
) -> list[BenchmarkResult]:
    """Run all benchmarks from all suites and return results.

    Never stops on failure — always completes the full run.
    """
    results: list[BenchmarkResult] = []

    for suite in suites:
        for benchmark in suite.benchmarks:
            logger.info("Running benchmark: %s", benchmark.id)
            try:
                output = adapter.complete(benchmark.prompt)
            except Exception as exc:
                logger.error("Benchmark %s failed: %s", benchmark.id, exc)
                results.append(
                    BenchmarkResult(
                        benchmark_id=benchmark.id,
                        score=0.0,
                        checks=[],
                        output=None,
                    )
                )
                continue

            check_results = [
                _execute_check(check, output, judge=judge, has_pro=has_pro)
                for check in benchmark.checks
            ]

            result = BenchmarkResult(
                benchmark_id=benchmark.id,
                score=0.0,
                checks=check_results,
                output=output,
            )
            result.score = score_benchmark(result)
            results.append(result)

    return results
