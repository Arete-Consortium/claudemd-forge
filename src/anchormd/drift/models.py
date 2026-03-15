"""Data models for agent drift detection."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class CheckType(StrEnum):
    """Types of benchmark checks."""

    PATTERN_PRESENT = "pattern_present"
    PATTERN_ABSENT = "pattern_absent"
    LLM_JUDGE = "llm_judge"
    LENGTH_RANGE = "length_range"
    JSON_VALID = "json_valid"
    CONTAINS_SECTIONS = "contains_sections"


class BenchmarkCheck(BaseModel):
    """A single check within a benchmark."""

    type: CheckType
    pattern: str | None = None
    message: str | None = None
    criteria: str | None = None
    threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    min_words: int | None = None
    max_words: int | None = None
    sections: list[str] | None = None


class BenchmarkDef(BaseModel):
    """A benchmark definition with prompt and checks."""

    id: str
    prompt: str
    checks: list[BenchmarkCheck]
    weight: float = Field(default=1.0, ge=0.0)


class BenchmarkSuite(BaseModel):
    """A collection of benchmark definitions."""

    version: int = 1
    benchmarks: list[BenchmarkDef]


class CheckResult(BaseModel):
    """Result of executing a single check."""

    type: CheckType
    passed: bool
    message: str | None = None
    score: float | None = None


class BenchmarkResult(BaseModel):
    """Result of running a single benchmark."""

    benchmark_id: str
    score: float = Field(ge=0.0, le=1.0)
    checks: list[CheckResult]
    output: str | None = None


class DriftSeverity(StrEnum):
    """Severity classification for drift detection."""

    CRITICAL = "critical"
    WARNING = "warning"
    STABLE = "stable"
    IMPROVED = "improved"


class RunRecord(BaseModel):
    """Record of a complete drift detection run."""

    run_id: str
    timestamp: str
    model: str
    score: float = Field(ge=0.0, le=1.0)
    delta: float
    severity: DriftSeverity
    results: list[BenchmarkResult]
