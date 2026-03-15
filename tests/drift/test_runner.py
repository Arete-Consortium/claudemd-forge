"""Tests for drift benchmark runner."""

from __future__ import annotations

from unittest.mock import MagicMock

from anchormd.drift.adapters.base import ModelAdapter
from anchormd.drift.models import (
    BenchmarkCheck,
    BenchmarkDef,
    BenchmarkSuite,
    CheckType,
)
from anchormd.drift.runner import (
    _check_contains_sections,
    _check_json_valid,
    _check_length_range,
    _check_pattern_absent,
    _check_pattern_present,
    _execute_check,
    run_benchmarks,
)


class FakeAdapter(ModelAdapter):
    def __init__(self, response: str = "Hello, world!") -> None:
        self._response = response

    def complete(self, prompt: str, system: str | None = None) -> str:
        return self._response

    def name(self) -> str:
        return "fake-model"


class TestCheckPatternPresent:
    def test_found(self) -> None:
        assert _check_pattern_present("Hello World", r"hello") is True

    def test_not_found(self) -> None:
        assert _check_pattern_present("Hello World", r"goodbye") is False

    def test_regex(self) -> None:
        assert _check_pattern_present("def foo_bar()", r"def \w+\(") is True

    def test_multiline(self) -> None:
        assert _check_pattern_present("line1\nline2", r"line1.*line2") is True


class TestCheckPatternAbsent:
    def test_absent(self) -> None:
        assert _check_pattern_absent("Hello World", r"goodbye") is True

    def test_present(self) -> None:
        assert _check_pattern_absent("Hello World", r"hello") is False


class TestCheckLengthRange:
    def test_within_range(self) -> None:
        assert _check_length_range("one two three", 1, 10) is True

    def test_below_min(self) -> None:
        assert _check_length_range("one", 5, None) is False

    def test_above_max(self) -> None:
        assert _check_length_range("one two three four five", None, 3) is False

    def test_no_bounds(self) -> None:
        assert _check_length_range("anything", None, None) is True


class TestCheckJsonValid:
    def test_valid_json(self) -> None:
        assert _check_json_valid('{"key": "value"}') is True

    def test_invalid_json(self) -> None:
        assert _check_json_valid("not json at all") is False

    def test_json_in_fence(self) -> None:
        output = '```json\n{"key": "value"}\n```'
        assert _check_json_valid(output) is True

    def test_json_in_bare_fence(self) -> None:
        output = '```\n{"key": "value"}\n```'
        assert _check_json_valid(output) is True


class TestCheckContainsSections:
    def test_all_present(self) -> None:
        output = "# Introduction\nSome text\n## Conclusion\nMore text"
        assert _check_contains_sections(output, ["Introduction", "Conclusion"]) is True

    def test_missing_section(self) -> None:
        output = "# Introduction\nSome text"
        assert _check_contains_sections(output, ["Introduction", "Missing"]) is False

    def test_bold_format(self) -> None:
        output = "**Introduction**\nSome text"
        assert _check_contains_sections(output, ["Introduction"]) is True

    def test_case_insensitive(self) -> None:
        output = "## introduction\ntext"
        assert _check_contains_sections(output, ["Introduction"]) is True


class TestExecuteCheck:
    def test_pattern_present_pass(self) -> None:
        check = BenchmarkCheck(type=CheckType.PATTERN_PRESENT, pattern="hello")
        result = _execute_check(check, "hello world")
        assert result.passed is True

    def test_pattern_present_fail(self) -> None:
        check = BenchmarkCheck(type=CheckType.PATTERN_PRESENT, pattern="goodbye")
        result = _execute_check(check, "hello world")
        assert result.passed is False

    def test_pattern_absent_pass(self) -> None:
        check = BenchmarkCheck(type=CheckType.PATTERN_ABSENT, pattern="goodbye")
        result = _execute_check(check, "hello world")
        assert result.passed is True

    def test_length_range_pass(self) -> None:
        check = BenchmarkCheck(type=CheckType.LENGTH_RANGE, min_words=1, max_words=10)
        result = _execute_check(check, "hello world")
        assert result.passed is True

    def test_json_valid_pass(self) -> None:
        check = BenchmarkCheck(type=CheckType.JSON_VALID)
        result = _execute_check(check, '{"valid": true}')
        assert result.passed is True

    def test_contains_sections_pass(self) -> None:
        check = BenchmarkCheck(type=CheckType.CONTAINS_SECTIONS, sections=["Intro"])
        result = _execute_check(check, "# Intro\ntext")
        assert result.passed is True

    def test_llm_judge_no_pro(self) -> None:
        check = BenchmarkCheck(type=CheckType.LLM_JUDGE, criteria="be helpful")
        result = _execute_check(check, "output", has_pro=False)
        assert result.passed is False
        assert "Pro tier" in (result.message or "")

    def test_llm_judge_no_judge(self) -> None:
        check = BenchmarkCheck(type=CheckType.LLM_JUDGE, criteria="be helpful")
        result = _execute_check(check, "output", has_pro=True, judge=None)
        assert result.passed is False
        assert "No judge" in (result.message or "")

    def test_llm_judge_success(self) -> None:
        judge = FakeAdapter(response='{"score": 0.9, "reasoning": "good"}')
        check = BenchmarkCheck(type=CheckType.LLM_JUDGE, criteria="be helpful", threshold=0.8)
        result = _execute_check(check, "output", has_pro=True, judge=judge)
        assert result.passed is True
        assert result.score == 0.9

    def test_custom_message(self) -> None:
        check = BenchmarkCheck(
            type=CheckType.PATTERN_PRESENT, pattern="hello", message="Custom msg"
        )
        result = _execute_check(check, "hello world")
        assert result.message == "Custom msg"


class TestRunBenchmarks:
    def test_basic_run(self) -> None:
        adapter = FakeAdapter("def hello_world():\n    pass")
        suite = BenchmarkSuite(
            benchmarks=[
                BenchmarkDef(
                    id="test_snake_case",
                    prompt="Write a function",
                    checks=[
                        BenchmarkCheck(type=CheckType.PATTERN_PRESENT, pattern=r"def \w+\("),
                    ],
                )
            ]
        )
        results = run_benchmarks(adapter, [suite])
        assert len(results) == 1
        assert results[0].score > 0
        assert results[0].output is not None

    def test_adapter_failure(self) -> None:
        adapter = MagicMock(spec=ModelAdapter)
        adapter.complete.side_effect = Exception("API down")
        suite = BenchmarkSuite(
            benchmarks=[
                BenchmarkDef(
                    id="test",
                    prompt="anything",
                    checks=[BenchmarkCheck(type=CheckType.PATTERN_PRESENT, pattern="x")],
                )
            ]
        )
        results = run_benchmarks(adapter, [suite])
        assert len(results) == 1
        assert results[0].score == 0.0

    def test_multiple_suites(self) -> None:
        adapter = FakeAdapter("output")
        suite1 = BenchmarkSuite(benchmarks=[BenchmarkDef(id="a", prompt="x", checks=[])])
        suite2 = BenchmarkSuite(benchmarks=[BenchmarkDef(id="b", prompt="x", checks=[])])
        results = run_benchmarks(adapter, [suite1, suite2])
        assert len(results) == 2

    def test_empty_suites(self) -> None:
        adapter = FakeAdapter()
        results = run_benchmarks(adapter, [])
        assert results == []
