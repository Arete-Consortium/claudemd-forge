"""Splice new anti-pattern bullets into an existing CLAUDE.md.

Finds the ## Anti-Patterns section, de-duplicates against existing bullets by
title, and returns the patched content + unified diff. Does not write to disk —
callers handle confirmation and I/O.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

_SECTION_HEADER = re.compile(r"^##\s+(?P<title>.+?)\s*$", re.MULTILINE)
_BULLET_TITLE = re.compile(r"^\s*[-*]\s+\*\*(?P<title>[^*]+)\*\*")


@dataclass
class PatchResult:
    original: str
    patched: str
    added: int
    skipped: int  # bullets skipped because they already exist
    diff: str

    @property
    def changed(self) -> bool:
        return self.original != self.patched


def _find_section(content: str, title: str) -> tuple[int, int] | None:
    """Return (start, end) char offsets of the named section (exclusive end), or None.

    The section runs from the line after the header to the start of the next ## header,
    or to end-of-file. The returned start is the offset *after* the header line's newline.
    """
    for m in _SECTION_HEADER.finditer(content):
        if m.group("title").lower().startswith(title.lower()):
            # Body starts at the end of the header line (after its trailing newline).
            body_start = content.find("\n", m.end()) + 1
            # Body ends at the next ## header, or EOF.
            next_match = _SECTION_HEADER.search(content, body_start)
            body_end = next_match.start() if next_match else len(content)
            return body_start, body_end
    return None


def _existing_bullet_titles(section_body: str) -> set[str]:
    """Extract lowercased bullet titles from an existing section's body."""
    titles: set[str] = set()
    for line in section_body.splitlines():
        m = _BULLET_TITLE.match(line)
        if m:
            titles.add(m.group("title").strip().lower())
    return titles


def _insert_position(content: str) -> int:
    """Pick where to insert a new Anti-Patterns section if none exists.

    Preference: before ## Dependencies, ## Git Conventions, or ## Security.
    Fall back to end-of-file.
    """
    for candidate in ("Dependencies", "Git Conventions", "Security", "CI/CD"):
        for m in _SECTION_HEADER.finditer(content):
            if m.group("title").lower().startswith(candidate.lower()):
                return m.start()
    return len(content)


def patch(content: str, new_bullets: list[str], section_name: str = "Anti-Patterns") -> PatchResult:
    """Splice new bullets into the named section of `content`.

    Skips bullets whose title is already present. If the section doesn't exist,
    a new one is inserted before Dependencies/Git Conventions/Security.
    """
    # Normalize: if someone passed full-line bullets, strip trailing newlines.
    new_bullets = [b.rstrip("\n") for b in new_bullets if b.strip()]

    section = _find_section(content, section_name)
    skipped = 0
    added = 0

    if section is None:
        # No existing section — build one from scratch.
        block_lines = [f"## {section_name}", ""] + new_bullets + [""]
        block = "\n".join(block_lines)
        if not block.endswith("\n"):
            block += "\n"
        insert_at = _insert_position(content)
        prefix = content[:insert_at].rstrip()
        suffix = content[insert_at:]
        # Ensure blank line separation.
        patched = prefix + "\n\n" + block + "\n" + suffix.lstrip("\n")
        added = len(new_bullets)
    else:
        body_start, body_end = section
        body = content[body_start:body_end]
        existing = _existing_bullet_titles(body)

        to_append: list[str] = []
        for bullet in new_bullets:
            m = _BULLET_TITLE.match(bullet)
            title = m.group("title").strip().lower() if m else bullet.strip().lower()
            if title in existing:
                skipped += 1
                continue
            to_append.append(bullet)
            existing.add(title)

        if not to_append:
            return PatchResult(
                original=content,
                patched=content,
                added=0,
                skipped=skipped,
                diff="",
            )

        # Append new bullets at the end of the section body, with a leading
        # blank line if the body doesn't already end with one.
        trimmed_body = body.rstrip("\n")
        appended = trimmed_body + "\n" + "\n".join(to_append) + "\n"
        # Preserve the trailing blank line pattern between sections.
        if body.endswith("\n\n"):
            appended += "\n"
        patched = content[:body_start] + appended + content[body_end:]
        added = len(to_append)

    diff = "".join(
        difflib.unified_diff(
            content.splitlines(keepends=True),
            patched.splitlines(keepends=True),
            fromfile="CLAUDE.md (original)",
            tofile="CLAUDE.md (patched)",
            n=3,
        )
    )

    return PatchResult(
        original=content,
        patched=patched,
        added=added,
        skipped=skipped,
        diff=diff,
    )
