"""Tests for the Anti-Patterns CLAUDE.md patcher."""

from __future__ import annotations

from anchormd.generators.patcher import patch


def test_patch_appends_to_existing_section() -> None:
    content = (
        "# demo\n\n## Anti-Patterns\n- **Existing rule** — already here\n\n## Dependencies\n- foo\n"
    )
    bullets = [
        "- **Always Read before Edit/Write** — Read first.",
        "- **Existing rule** — duplicate skipped",
    ]
    result = patch(content, bullets)
    assert result.added == 1
    assert result.skipped == 1
    assert "Always Read before Edit/Write" in result.patched
    # The new bullet goes into the existing section, not a new one.
    assert result.patched.count("## Anti-Patterns") == 1


def test_patch_creates_section_when_missing() -> None:
    content = "# demo\n\n## Project Overview\nhi\n\n## Dependencies\n- foo\n"
    bullets = ["- **New rule** — do this"]
    result = patch(content, bullets)
    assert result.added == 1
    # Section was created.
    assert "## Anti-Patterns" in result.patched
    # Dependencies still present and after Anti-Patterns.
    ap_idx = result.patched.index("## Anti-Patterns")
    dep_idx = result.patched.index("## Dependencies")
    assert ap_idx < dep_idx


def test_patch_creates_section_at_eof_if_no_anchor() -> None:
    content = "# demo\n\n## Project Overview\nhi\n"
    bullets = ["- **New rule** — do this"]
    result = patch(content, bullets)
    assert "## Anti-Patterns" in result.patched
    assert "New rule" in result.patched


def test_patch_nothing_to_add_returns_unchanged() -> None:
    content = "# demo\n\n## Anti-Patterns\n- **X** — already here\n\n## Dependencies\n- foo\n"
    bullets = ["- **X** — duplicate"]
    result = patch(content, bullets)
    assert result.changed is False
    assert result.added == 0
    assert result.skipped == 1
    assert result.diff == ""


def test_patch_case_insensitive_dedupe() -> None:
    content = "# demo\n\n## Anti-Patterns\n- **Always Read Before Edit** — original\n"
    bullets = ["- **always read before edit** — lowercase variant"]
    result = patch(content, bullets)
    assert result.added == 0
    assert result.skipped == 1


def test_patch_diff_generated() -> None:
    content = "# demo\n\n## Anti-Patterns\n- **Old** — a\n\n## Dependencies\n- foo\n"
    bullets = ["- **New** — b"]
    result = patch(content, bullets)
    assert result.diff
    assert "+- **New** — b" in result.diff
