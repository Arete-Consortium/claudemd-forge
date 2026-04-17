"""Tests for the gotcha → anti-pattern suggestion mapper."""

from __future__ import annotations

from anchormd.analyzers.suggestions import (
    Suggestion,
    format_anti_patterns_block,
    suggest_for,
)


def test_edit_without_read_maps_to_suggestion() -> None:
    s = suggest_for("Edit", "<tool_use_error>File has not been read yet. Read it first before writing.")
    assert s is not None
    assert "Read before Edit" in s.title


def test_write_maps_to_distinct_suggestion() -> None:
    s = suggest_for("Write", "File has not been read yet before writing")
    assert s is not None
    assert "overwriting" in s.title.lower()


def test_large_file_read_maps_to_offset_suggestion() -> None:
    s = suggest_for("Read", "File content (40000 tokens) exceeds maximum allowed tokens (25000)")
    assert s is not None
    assert "offset" in s.body.lower()


def test_unknown_pattern_returns_none() -> None:
    assert suggest_for("Bash", "some obscure error nobody has seen") is None


def test_tool_mismatch_returns_none() -> None:
    # 'has not been read yet' is Edit/Write specific — Read shouldn't match.
    assert suggest_for("Read", "has not been read yet") is None


def test_format_anti_patterns_block_dedupes() -> None:
    s = Suggestion(title="Always Read before Edit/Write", body="x")
    out = format_anti_patterns_block([s, s, s])
    assert out.count("Always Read before Edit/Write") == 1


def test_format_empty_returns_empty() -> None:
    assert format_anti_patterns_block([]) == ""


def test_format_renders_header_and_bullets() -> None:
    suggestions = [
        Suggestion(title="A", body="do A"),
        Suggestion(title="B", body="do B"),
    ]
    out = format_anti_patterns_block(suggestions)
    assert "## Anti-Patterns" in out
    assert "- **A** — do A" in out
    assert "- **B** — do B" in out
