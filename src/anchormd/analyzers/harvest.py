"""Session harvester — pulls recurring gotchas from Claude Code JSONL transcripts.

Reads `~/.claude/projects/<slug>/*.jsonl` for a given project directory,
extracts tool errors, normalizes them, and surfaces the ones that keep
happening — those are the anti-patterns that belong in CLAUDE.md.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from anchormd.analyzers.suggestions import Suggestion, suggest_for


@dataclass
class Gotcha:
    signature: str
    tool: str
    count: int
    sessions: int  # number of distinct sessions where this occurred
    examples: list[str] = field(default_factory=list)
    suggestion: Suggestion | None = None


@dataclass
class HarvestReport:
    project_path: Path
    transcript_dir: Path | None
    sessions_scanned: int = 0
    tool_calls_scanned: int = 0
    tool_errors: int = 0
    gotchas: list[Gotcha] = field(default_factory=list)


def _project_slug(project_path: Path) -> str:
    """~/.claude/projects uses dash-escaped absolute paths as dir names."""
    resolved = project_path.resolve()
    return "-" + str(resolved).strip("/").replace("/", "-")


def _find_transcript_dir(project_path: Path) -> tuple[Path | None, str | None]:
    """Locate transcripts for project_path.

    Returns (dir, cwd_filter):
      - exact slug match: (dir, None) — use all events
      - parent slug match: (dir, str(project_path)) — filter events by cwd
      - no match: (None, None)
    """
    slug = _project_slug(project_path)
    base = Path.home() / ".claude" / "projects"
    candidate = base / slug
    if candidate.is_dir():
        return candidate, None
    # Walk up to parents (e.g. ~/projects vs ~/projects/Dossier).
    parts = slug.strip("-").split("-")
    while parts:
        parts.pop()
        parent_slug = "-" + "-".join(parts) if parts else ""
        if parent_slug and (base / parent_slug).is_dir():
            return base / parent_slug, str(project_path.resolve())
    return None, None


_NOISE = [
    (re.compile(r"/[\w\-\./]+"), "<PATH>"),
    (re.compile(r"\b[0-9a-f]{8,}\b"), "<HEX>"),
    (re.compile(r"\b\d+\b"), "<N>"),
    (re.compile(r"\s+"), " "),
]


def _normalize(error_text: str) -> str:
    """Strip paths, hex IDs, and numbers so similar errors cluster together."""
    sig = error_text.strip()[:400]
    for pattern, placeholder in _NOISE:
        sig = pattern.sub(placeholder, sig)
    return sig[:160]


def _extract_errors_from_jsonl(
    jsonl_path: Path, cwd_filter: str | None = None
) -> list[tuple[str, str, str]]:
    """Return list of (tool_name, normalized_signature, raw_excerpt).

    If cwd_filter is given, only include errors from events where cwd starts with it.
    """
    errors: list[tuple[str, str, str]] = []
    try:
        with jsonl_path.open() as f:
            tool_names: dict[str, str] = {}
            tool_cwd: dict[str, str] = {}
            for line in f:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                event_cwd = event.get("cwd")
                msg = event.get("message") or {}
                content = msg.get("content")
                if not isinstance(content, list):
                    continue
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    if item.get("type") == "tool_use":
                        tid = item.get("id", "")
                        tool_names[tid] = item.get("name", "?")
                        if event_cwd:
                            tool_cwd[tid] = event_cwd
                    elif item.get("type") == "tool_result" and item.get("is_error"):
                        tool_id = item.get("tool_use_id", "")
                        if cwd_filter and not tool_cwd.get(tool_id, "").startswith(cwd_filter):
                            continue
                        tool_name = tool_names.get(tool_id, "?")
                        raw = item.get("content")
                        if isinstance(raw, list):
                            raw = " ".join(
                                str(b.get("text", "")) for b in raw if isinstance(b, dict)
                            )
                        raw_text = str(raw or "")
                        sig = _normalize(raw_text)
                        if sig:
                            errors.append((tool_name, sig, raw_text[:200]))
    except OSError:
        pass
    return errors


def harvest(
    project_path: Path,
    min_count: int = 2,
    limit: int = 10,
) -> HarvestReport:
    """Scan a project's Claude Code transcripts for recurring tool errors."""
    transcript_dir, cwd_filter = _find_transcript_dir(project_path)
    report = HarvestReport(project_path=project_path, transcript_dir=transcript_dir)

    if transcript_dir is None:
        return report

    # signature -> (tool, count, set(session_ids), examples)
    agg: dict[str, dict] = defaultdict(
        lambda: {"tool": "?", "count": 0, "sessions": set(), "examples": []}
    )

    for jsonl_path in transcript_dir.glob("*.jsonl"):
        report.sessions_scanned += 1
        session_id = jsonl_path.stem
        errors = _extract_errors_from_jsonl(jsonl_path, cwd_filter=cwd_filter)
        report.tool_errors += len(errors)
        for tool, sig, example in errors:
            key = f"{tool}::{sig}"
            agg[key]["tool"] = tool
            agg[key]["count"] += 1
            agg[key]["sessions"].add(session_id)
            if len(agg[key]["examples"]) < 3:
                agg[key]["examples"].append(example)

    # Also count all tool_use entries for denominator (optional, slow).
    # For now, skip to keep scan fast — counts come from errors only.

    ranked = sorted(agg.items(), key=lambda kv: kv[1]["count"], reverse=True)
    for key, data in ranked:
        if data["count"] < min_count:
            continue
        tool, sig = key.split("::", 1)
        report.gotchas.append(
            Gotcha(
                signature=sig,
                tool=tool,
                count=data["count"],
                sessions=len(data["sessions"]),
                examples=list(data["examples"]),
                suggestion=suggest_for(tool, sig),
            )
        )
        if len(report.gotchas) >= limit:
            break

    return report
