"""Map recurring tool-error gotchas to CLAUDE.md anti-pattern suggestions.

The matcher is pattern-based rather than signature-equality so that new error
text variants still route to the right advice. Unmatched gotchas fall through
to a generic "investigate and document" suggestion.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Suggestion:
    title: str  # short headline for the anti-pattern bullet
    body: str  # one-sentence guidance
    section: str = "Anti-Patterns"  # target CLAUDE.md section


@dataclass(frozen=True)
class _Rule:
    tool: str | None  # None = match any tool
    pattern: re.Pattern[str]
    suggestion: Suggestion


_RULES: tuple[_Rule, ...] = (
    _Rule(
        tool="Edit",
        pattern=re.compile(r"has not been read yet", re.I),
        suggestion=Suggestion(
            title="Always Read before Edit/Write",
            body=(
                "The Edit tool refuses to operate on files that haven't been "
                "Read in the current session — Read first, then Edit."
            ),
        ),
    ),
    _Rule(
        tool="Write",
        pattern=re.compile(r"has not been read yet", re.I),
        suggestion=Suggestion(
            title="Always Read before overwriting an existing file",
            body=(
                "Write refuses to clobber an existing file until it's been "
                "Read in-session — prevents accidental overwrites."
            ),
        ),
    ),
    _Rule(
        tool="Edit",
        pattern=re.compile(r"has been modified since read", re.I),
        suggestion=Suggestion(
            title="Re-Read before Edit if the file may have changed",
            body=(
                "If another tool or the user modified a file after your last "
                "Read, re-Read it before Edit or the patch will be rejected."
            ),
        ),
    ),
    _Rule(
        tool="Read",
        pattern=re.compile(r"exceeds maximum allowed tokens", re.I),
        suggestion=Suggestion(
            title="Use offset/limit when reading large files",
            body=(
                "Files over the token ceiling must be read in ranges with "
                "`offset` and `limit` — a full Read will fail."
            ),
        ),
    ),
    _Rule(
        tool="Read",
        pattern=re.compile(r"file does not exist", re.I),
        suggestion=Suggestion(
            title="Verify paths with Glob before Read",
            body=(
                "When a path is uncertain, run Glob or `ls` first — a Read on "
                "a missing file wastes a turn."
            ),
        ),
    ),
    _Rule(
        tool="WebFetch",
        pattern=re.compile(r"status code", re.I),
        suggestion=Suggestion(
            title="Document flaky external URLs",
            body=(
                "If WebFetch consistently fails against a given host, note "
                "the alternative (cache, archive, proxy) in CLAUDE.md."
            ),
        ),
    ),
    _Rule(
        tool="Bash",
        pattern=re.compile(r"\brm\b.*real rm", re.I),
        suggestion=Suggestion(
            title="Use `trash` instead of `rm` on this system",
            body=(
                "`rm` is aliased to block real deletions — use `trash` for "
                "reversible deletes, or `/usr/bin/rm` if truly required."
            ),
        ),
    ),
    _Rule(
        tool="Bash",
        pattern=re.compile(r"command not found|: not found", re.I),
        suggestion=Suggestion(
            title="Verify binary paths before invoking",
            body=(
                "Tools installed outside $PATH (flyctl, gh, .venv bins) must "
                "be called by absolute path — list them in Common Commands."
            ),
        ),
    ),
    _Rule(
        tool="Bash",
        pattern=re.compile(r"doesn't want to proceed|tool use was (rejected|denied)", re.I),
        suggestion=Suggestion(
            title="Pre-check risky commands with the user",
            body=(
                "Commands that were repeatedly denied should either be in the "
                "permission allowlist or stated explicitly before running."
            ),
        ),
    ),
)


def suggest_for(tool: str, signature: str) -> Suggestion | None:
    """Return the best matching suggestion for a gotcha, or None if no rule hits."""
    for rule in _RULES:
        if rule.tool and rule.tool != tool:
            continue
        if rule.pattern.search(signature):
            return rule.suggestion
    return None


def dedupe(suggestions: list[Suggestion]) -> list[Suggestion]:
    """De-duplicate by (title, section) while preserving order."""
    seen: set[tuple[str, str]] = set()
    unique: list[Suggestion] = []
    for s in suggestions:
        key = (s.title, s.section)
        if key in seen:
            continue
        seen.add(key)
        unique.append(s)
    return unique


def format_anti_patterns_block(suggestions: list[Suggestion]) -> str:
    """Render suggestions as a markdown block ready to paste under ## Anti-Patterns."""
    if not suggestions:
        return ""
    unique = dedupe(suggestions)
    lines = ["## Anti-Patterns (harvested from session history)", ""]
    for s in unique:
        lines.append(f"- **{s.title}** — {s.body}")
    lines.append("")
    return "\n".join(lines)


def format_bullets(suggestions: list[Suggestion]) -> list[str]:
    """Return bullet lines only — no section header. For merging into an existing section."""
    return [f"- **{s.title}** — {s.body}" for s in dedupe(suggestions)]
